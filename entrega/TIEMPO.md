# Tiempo

| Caso | Horas | Comentario |
|---|---|---|
| Lectura de contexto y setup (`npm ci`, datos) | 0,5 h | Enunciados, glosario, estructura de entrega, primer vistazo a los CSV. |
| Caso 1 · Inbound MX | 2,0 h | El más denso: análisis de 6 CSV cruzados, refactor de dos User Events a un módulo compartido, 24 tests nuevos (incluido el *replay* de los datos) y la nota. La parte difícil fue separar lo que es del gate de lo que es del bundle. |
| Caso 2 · Marketplace | 1,5 h | Volumen grande (83k filas) pero con hipótesis claras una vez cruzado el log del iPaaS con las SO. Lo que más tiempo llevó fue clasificar los backorders por situación de stock y redactar el plan con dueños y trade-offs. |
| Caso 3 · P2P regional | 1,0 h | Diseño + matriz + decisiones. El diagrama se generó por script (SVG) y se iteró dos veces sobre el render. |
| Entrega (USO-DE-IA, TIEMPO, revisión final) | 1h | Verificación de estructura, `npm test` final, y una pasada de revisión de la nota y el diagnóstico cifra por cifra contra los scripts: encontró dos imprecisiones (ventas antes del LC en el caso 1; "ni compra" sin datos de compras en el caso 2) que corregí. |
| **Total** | **6 h** | |

Está por debajo de las 8–10 h sugeridas porque trabajé con IA como par durante todo el challenge (detalle en `USO-DE-IA.md`): el análisis de datos y el borrador de código y documentos salieron rápido; mi tiempo fue sobre todo dirigir, verificar contra datos y código, y corregir. Las horas incluyen esa revisión.

## Qué me resultó confuso

- **Caso 1.** El repo no permite verificar en qué contexto de ejecución corre el job *Receive Inbound Shipment*; la causa se infiere de los datos (las 4 recepciones con LC incompleto son del job) y del deployment, y la dejo como prueba obligatoria en sandbox. El glosario dice que en MX el lote *es* el pedimento, pero el maestro de pedimentos vincula ítem + depósito + lote → pedimento, lo que sugiere que podrían ser distintos: lo marqué como pregunta al proveedor. `receipt_lines.csv` trae `regulated`, `mfg_lot` y `expiry_date` sin ninguna anomalía en los datos; asumí que es contexto para el caso 3 y no agregué esa regla al gate (sólo la menciono).
- **Caso 2.** Todas las SO tienen una sola línea de 1 unidad, así que "órdenes" y "unidades" coinciden y no se puede ver el efecto de órdenes multi-línea ni de compromisos parciales. Las TO recibidas tienen exactamente 3 o 12 días de demora, sin valores intermedios: lo interpreté como dos modos de trabajo (recepción al llegar vs. por lotes). El snapshot de inventario es de un solo día, por lo que la causa D (stock disponible sin comprometer) se infiere de la fecha de recepción de la TO vs. la de creación de la SO; para confirmar hace falta ver el `commitinventory` que manda el iPaaS. No queda claro quién cerró a mano las 35 SO duplicadas ni con qué criterio.
- **Caso 3.** La consigna pide "las particularidades de cada país las sabés vos": dejé como supuestos explícitos lo que no puedo afirmar con certeza (si la factura electrónica de AR/CO lleva dato aduanero, el alcance de la trazabilidad ANMAT, qué conceptos de importación se capitalizan).
- **Estructura de entrega.** `ENTREGA.md` pide `diagrama.(png|svg|pdf|md)`: entrego SVG (fuente) y PNG (vista rápida) del mismo diagrama.
