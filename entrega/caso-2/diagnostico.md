# Caso 2 · Diagnóstico — ventas entregadas que no se facturan

Todas las cifras salen de `analisis/analisis_caso2.py` sobre `data/` (corte 30-09-2026). Los datos son internamente consistentes (depósito de la SO = `fulfillment_type`, ítem y cantidad = orden del marketplace, `committed` del snapshot = suma de líneas abiertas), así que el problema no es de mapeo de órdenes sino de **lo que pasó después de crearlas**.

## Resumen

De 24.473 órdenes que el marketplace marca como entregadas, **2.622 no tienen factura en NetSuite**. No es un problema sino seis, con dueños distintos:

| # | Situación de la orden entregada | Órdenes | % | Causa | Dueño |
|---|---|---|---|---|---|
| — | SO despachada, *Pending Billing*, entregada hace < 48 h | 1.567 | 59,8 % | Cola normal de facturación | — (verificar capacidad del job) |
| — | SO comprometida, falta correr el despacho | 60 | 2,3 % | Cola normal de despacho | — |
| D | Backorder con **stock disponible** en `AR-MKP-FC` y línea sin comprometer | 495 | 18,9 % | Compromiso no se rehízo al recibir la TO | NetSuite |
| C | Backorder esperando una **Transfer Order recibida a medias** | 299 | 11,4 % | Recepción de TO incompleta hace 20–28 días | Logística |
| B | **Sin Sales Order**: el iPaaS descartó la orden (`ITEM_NOT_FOUND`) | 160 | 6,1 % | 12 SKUs nuevos sin mapear + descarte silencioso | Catálogo + iPaaS/partner |
| E | Backorder sin stock en NetSuite en ningún lado | 41 | 1,6 % | El marketplace vendió stock que NetSuite no tiene | Logística + Finanzas |
| A | **+280 SO duplicadas** en backorder que *no son ventas* | (280) | — | Reintentos del iPaaS tras `TIMEOUT` sin idempotencia | iPaaS/partner (+ guard en NetSuite) |

Lo que AR ve como "más de mil órdenes entregadas en backorder" son **1.115 SO = 835 ventas reales (C+D+E) + 280 duplicados**. El trabajo real sobre backorders es de 835 líneas (835 unidades, todas de 1 unidad), más 160 órdenes que AR **no ve** porque nunca llegaron a NetSuite. Las 1.627 restantes se facturan solas si los jobs de despacho y facturación corren.

Fuera de la foto de AR pero urgente para el evento: **355 órdenes pagadas de despacho propio (`AR-CD-CENTRAL`) sin stock en ningún depósito ni en tránsito**, 11 ítems sin ninguna TO en el mes (no tenemos datos de compras para saber si hay reposición en camino). Es quiebre real, no un tema de facturación.

## Causa A · Duplicados por reintento tras timeout (280 SO abiertas + 35 ya cerradas a mano)

- 92 órdenes tienen más de una SO (315 sobrantes: 280 *Pending Fulfillment*, 35 *Closed*; alguien ya venía cerrando a mano). En **las 92, #SO = #TIMEOUT + 1**: cada intento que el iPaaS registró como `TIMEOUT` (read timeout a 120 s) **sí creó la SO en NetSuite**; el reintento a los 2 minutos creó otra. Peor caso: orden `2000014732`, **39 SO**.
- De 216 órdenes con `TIMEOUT`, el 43 % quedó duplicada. Los 406 `RATE_LIMIT` (429, concurrencia SuiteTalk) sobre 260 órdenes **no** duplicaron: el 429 rechaza antes de crear. El problema es exclusivamente el timeout.
- La primera SO de cada orden está facturada (85) o por facturar (7): la venta real está bien. Los duplicados no comprometen stock, pero inflan el backorder de AR y, si alguien "fuerza stock" para facturarlos, **se facturan dos veces** (0 hasta hoy).
- Los timeouts se concentran 22:00–01:00 y 11:00–19:00 y pican el 17-09 (52): coincide con ventanas de procesos batch y de concurrencia alta. Con processors fijos, la integración compite con scheduled/M/R; es la hipótesis a confirmar con APM / script execution logs (qué corre sincrónico al crear una SO y cuánto tarda).
- El partner tiene razón en que "funciona según lo especificado": la especificación no tiene idempotencia (`externalId` = `mp_order_id`, o consulta antes de reintentar). Eso es un defecto de diseño de la integración, no de datos maestros.

## Causa B · 160 órdenes que nunca entraron (`ITEM_NOT_FOUND`)

- 12 SKUs del marketplace no están en `item_mapping` (ninguno es ítem inactivo: simplemente no existe el mapeo). 160 órdenes, todas `delivered`, todas fulfillment marketplace, desde el 01-09 hasta el 26-09: **26 días sin que nadie lo detectara**.
- El iPaaS reintenta 3 veces el mismo error determinístico y descarta. No hay cola de cuarentena ni alerta a Andina; el partner lo ve en su log, AR no lo ve en ningún lado. El dato maestro es de Andina, pero el descarte silencioso es del flujo.

## Causa C · Transfer Orders recibidas a medias (299 SO)

- 13 TO `AR-CD-CENTRAL → AR-MKP-FC` creadas entre el 02-09 y el 10-09 están *Pending Receipt* con **703 unidades enviadas y no recibidas**, hace 20–28 días. En las 46 TO recibidas, el tiempo creación→recepción es bimodal: 3 días (30) o 12 días (16): la recepción en NetSuite es manual o por lotes, no sigue la confirmación de inbound del marketplace.
- 299 ventas entregadas esperan ese stock (10 ítems). Recibir el saldo cubre 238; en 4 ítems (`0171`, `0107`, `0134`, `0225`) faltan 61 unidades aun recibiendo todo → pasan a la causa E.
- Logística tiene razón en que "mandamos todo": está enviado. Pero no está **recibido** en NetSuite, y el marketplace ya lo vendió.

## Causa D · Stock disponible, línea sin comprometer (495 SO)

- 495 líneas en backorder sobre 13 ítems que hoy tienen **1.930 unidades disponibles** en `AR-MKP-FC`. En el 100 % de los casos la TO que trajo el stock se recibió **después** de crear la SO. NetSuite debería haber comprometido esas líneas al recibir; no lo hizo.
- Candidatos a confirmar en la cuenta: (1) el iPaaS crea la línea con *Commit* = *Do Not Commit* o *Complete Qty*; (2) la recepción de TO se hace por una vía que no dispara reasignación; (3) la reasignación corre en un proceso que no está llegando (processors). La corrección operativa es la misma en los tres casos: re-comprometer; la estructural depende de cuál sea.

## Causa E · El marketplace entregó stock que NetSuite no tiene (41 + 61 SO)

- 41 ventas entregadas desde `AR-MKP-FC` sobre 6 ítems con **0 on hand, 0 comprometido, 0 en tránsito en ambos depósitos y sin TO en el mes**. Más las 61 unidades de C que no se cubren recibiendo. El marketplace tiene stock físico que NetSuite no registra: devoluciones reingresadas en el FC, diferencias de conteo o envíos sin TO. Hace falta conciliar el reporte de inventario del marketplace contra NetSuite y ajustar; después se despacha y factura.

## Lo que no es problema

1.567 SO *Pending Billing* están despachadas y entregadas hace 0–48 h: es la cola normal; 60 están comprometidas esperando el despacho. Hay que vigilar que los jobs de despacho/facturación tengan processors en los picos, pero no requieren acción manual.

## Lo que me falta saber

- Payload del iPaaS: ¿manda `externalId`? ¿qué valor de *commit* en la línea? ¿quién decidió el timeout de 120 s y el reintento cada 2 min?
- Qué corre sincrónicamente al crear una SO (User Events, workflows, bundle de localización) y el perfil de concurrencia/processors en las ventanas de timeout.
- Quién recibe las TO en NetSuite, con qué documento del marketplace, y por qué hubo recepciones parciales.
- Acceso al reporte de stock del marketplace (para E) y quién cerró a mano las 35 SO duplicadas y con qué criterio.
- Regla fiscal/contable para facturar en octubre entregas de septiembre (fecha de comprobante vs. entrega; devengamiento).
