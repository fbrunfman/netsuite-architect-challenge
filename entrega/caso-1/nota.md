# Caso 1 · La recepción que no frena — nota

Evidencia reproducible: `analisis/analisis_caso1.py` (sobre `data/`) y `__tests__/replay_jul_sep_data.test.js`, que pasa los 48 Item Receipts de jul–sep por el gate corregido reconstruyendo el embarque **a la fecha de recepción**.

## Qué encontré y cuánto impacta

Logística tiene razón: el sistema no los frenó. Son tres causas independientes.

1. **El job masivo *Receive Inbound Shipment* nunca pasó por el gate (→ Costos).** El deployment del User Event tenía una lista blanca de contextos (`CSVIMPORT|RESTWEBSERVICES|SUITELET|USERINTERFACE|WEBSERVICES`) que no incluye el contexto en background con que corre el job, y el gate del Inbound Shipment sólo deshabilita un botón en modo VIEW: la página masiva no lo ve. Resultado: 4 de las 17 recepciones por job entraron con landed cost incompleto; 0 de las 31 por *Receive page*. `IR-MX-00010` y `IR-MX-00038` (INBSHIP-0010/-0040) **sin ninguna fila de landed cost, todavía *Pending* al cierre, y ya con 21 facturas / 317 unidades vendidas a costo sin importación**; `IR-MX-00017` y `IR-MX-00022` con los 6 costos cargados y confirmados 5–8 días después de recibir (USD 6.866 + MXN 40.058 que entraron tarde; en -0026, 2 facturas / 22 unidades se vendieron antes). Los otros 13 pasaron porque el embarque casualmente estaba listo.
2. **La recepción directa no alimenta el maestro de pedimentos (→ Fiscal).** Las 8 recepciones `direct` (8/8, 65 líneas, 11.779 unidades) no tienen fila en `pedimento_master`; las 40 por puerto sí, todas. Sus lotes y segmentos están correctos (lote = pedimento), así que el gate las deja pasar con razón. El bundle MX parece crear el maestro desde el flujo puerto → transferencia, no desde un Item Receipt directo al depósito final. Efecto: **134 de 655 CFDI (20,5 %, 2.450 unidades) timbrados sin `numero_pedimento`, el 100 % de ellos sobre lotes de recepción directa** y creciendo con la adopción del flujo: 3 en julio, 32 en agosto, 99 en septiembre.
3. **El segmento de aduana se validaba sólo en cabecera (→ Contabilidad).** 9 líneas en 4 recepciones (`IR-MX-00008/-00011/-00021/-00044`, de ambos orígenes) tienen cabecera con segmento y línea vacía: 2.200 unidades (3,3 %) quedan fuera del reporte por segmento y esos 4 pedimentos no cuadran cabecera vs. líneas (p. ej. 269061588405817: 2.175 vs 1.063).

Además, diseño *fail-open*: parámetro "Confirmed id" vacío ⇒ R2 se saltea con un `log.error`; embarque no encontrado ⇒ `return`; reglas y parámetros duplicados en dos scripts (drift); switches *warn-only* que cualquier admin apaga sin rastro.

## Qué cambié (`npm test`: 37 tests, 16 de ellos fallan contra el código original)

- `customscript_acme_itemreceipt_gate_ue.xml`: **sin `executioncontext`** ⇒ corre en todos los contextos (job, scheduled, M/R, workflow, CSV, WS). Test `deployment.test.js` lo fija.
- `acme_inbship_rules.js` (nuevo): única fuente de reglas, usada por ambos UEs. **R4** segmento en cabecera **y en cada línea recibida** (ignora líneas con `itemreceive` desmarcado o qty 0). **R5** lote (inventory detail) = número de aduana, con parámetro de subsidiarias (MX) y switch *warn-only*. Formato del número de aduana por regex parametrizable (default pedimento 15 dígitos, espacios ignorados).
- *Fail closed*: parámetro faltante, embarque no leído o error de SuiteQL ⇒ bloquea (`ACME_GATE_CONFIG`/`_SHIPMENT_NOT_FOUND`/`_ERROR`). Checkbox devuelto como `'F'` se interpreta como apagado. Los *warn-only* loguean el contexto de ejecución.
- El gate del Inbound Shipment queda como ayuda de UI, con el mismo módulo de reglas y mensaje aclarando que el control real está en el Item Receipt.

**No se resuelve con código en este repo:** (a) que el maestro de pedimentos se cree para recepciones directas — es del bundle (o se construye un afterSubmit propio que lo pueble, sólo si el proveedor confirma el record/campos y que su CFDI lo respeta); (b) remediar lo ya ocurrido: cargar y confirmar LC de INBSHIP-0010/-0040 y revisar el recosteo de lo vendido de -0018/-0026 con Costos; poblar el maestro para las 65 líneas y, con Fiscal, cancelar y sustituir (relación 04) los 134 CFDI o emitir lo que el SAT admita; completar el segmento en las 9 líneas; (c) gobierno: cambiar los switches *warn-only* sólo por change request, y definir si el flujo directo es política o excepción.

## Qué probaría en sandbox antes de producción

Recibir un embarque no listo por **Receive page, job masivo, CSV import y SuiteTalk** y comprobar que las 4 vías bloquean y que `runtime.executionContext` del job queda en el audit log; recepción parcial (líneas desmarcadas) y segunda recepción del mismo embarque; ítem no lotificado y lote con espacios; verificar el **internal id real de "Confirmed"** en sandbox vs. prod; un IR de AR/CO (lot rule no aplica); el job con 20+ embarques (performance del SuiteQL por IR, cómo reporta el error por línea); e **invariante de datos**: SuiteQL que cruce IR de recepción directa vs. maestro de pedimentos, como alerta diaria hasta que el bundle lo cubra.

## Qué le preguntaría al proveedor del bundle MX

1. ¿Qué evento crea las filas del maestro de pedimentos (Item Receipt en depósito de puerto, Transfer Order, Item Receipt a cualquier depósito)? ¿Por qué no se crean en una recepción directa al depósito final? 2. ¿Puedo crear/actualizar ese custom record por script o CSV sin romper el timbrado; cuál es la clave (ítem + depósito + lote)? 3. Al timbrar, si no encuentra pedimento ¿por qué timbra igual en vez de frenar? ¿Hay un modo "bloquear"? 4. ¿Qué formato exige para el lote (15 dígitos sin espacios)? 5. Para CFDI ya timbrados sin pedimento, ¿qué remediación soportan (cancelación con sustitución)? 6. ¿Qué pasa con transferencias entre MX-CD-QRO y MX-CD-MTY: el maestro sigue al lote al nuevo depósito?
