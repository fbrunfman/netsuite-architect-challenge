# Caso 2 · Respuestas a los stakeholders

## A la Líder de Cuentas a Cobrar

Asunto: RE: URGENTE - órdenes entregadas sin facturar

Hola,

Revisé las 2.622 órdenes entregadas sin factura al 30-09. Lo bueno: 1.627 ya están despachadas o comprometidas y se facturan con los jobs de estos días. Lo que está trabado de verdad son 835 ventas, más 160 que nunca entraron a NetSuite (SKUs nuevos sin mapear) y que hoy no ves en ningún lado.

Las "más de mil" en backorder incluyen 280 Sales Orders duplicadas que generó la integración al reintentar: la venta real de cada una ya está facturada. Las cierro hoy; **no hay que facturarlas** porque sería facturar dos veces. Te paso una muestra de 10 para que valides conmigo.

Sobre "despachar a mano o forzar stock": no lo voy a hacer a ciegas, porque es la forma de facturar duplicados y de esconder una diferencia de inventario que vuelve el mes que viene. Sí vamos a destrabar todo con las herramientas correctas: recibir 13 transferencias que quedaron a medias (238 órdenes), re-comprometer 495 líneas que tienen stock disponible, reprocesar las 160 sin mapeo, y para 102 unidades que el marketplace vendió y NetSuite no tiene, un ajuste de inventario aprobado por Finanzas. Plan día por día en `plan.md`.

Para el día 1 te comprometo ~2.500 de las 2.622; las ~100 del ajuste dependen de la conciliación con el marketplace (día 2–4). Necesito de tu lado: confirmar con Impuestos la fecha de factura para entregas de septiembre que facturemos en octubre, y una persona que valide la lista de duplicados.

Desde hoy vas a tener una saved search "entregadas sin factura" por causa, para que el número lo veamos los dos igual.

## Al Jefe de Logística

Asunto: RE: URGENTE - órdenes entregadas sin facturar

Hola,

Tenés razón en lo central: la mercadería está en el marketplace y el marketplace la vendió. El problema no es que falte stock sino que NetSuite no lo tiene registrado como recibido, y por eso no deja despachar ni facturar. No te pido frenar transferencias ni cambiar cómo arman los envíos; te pido terminar tres cosas que ya están en curso:

1. **13 Transfer Orders a `AR-MKP-FC` creadas entre el 02-09 y el 10-09 están recibidas a medias**: 703 unidades enviadas y no recibidas, hace 20–28 días. Hay 299 ventas entregadas esperándolas. ¿Pueden recibirlas contra la confirmación de inbound del marketplace mañana? Es una hora de trabajo. Si el marketplace confirmó menos de lo enviado, cerramos el saldo y lo tratamos como diferencia.
2. **10 ítems donde el marketplace vendió stock que NetSuite no tiene** (102 unidades, lista adjunta). Necesito el reporte de inventario del marketplace para conciliar y hacer un ajuste aprobado por Finanzas. No es culpa de nadie; es que el FC tiene movimientos (devoluciones, conteos) que no estamos registrando.
3. **355 órdenes pagadas de despacho propio sin stock en ningún depósito** (11 ítems, sin transferencia ni compra en el mes). Esto sí es quiebre real y llega al evento de la semana que viene; te lo paso para que lo veas con Comercial.

Para que no se repita, propongo recibir las TO dentro de las 24 h de la confirmación del marketplace (idealmente automático desde el iPaaS, en una segunda etapa) y una alerta de TO con más de 5 días en tránsito. Lo vemos después del evento.

## Al Project Manager del partner

Asunto: RE: RE: URGENTE - órdenes entregadas sin facturar

Hola,

Coincido en que la integración hace lo especificado y en que el mapeo de SKUs es dato maestro de Andina: hoy cargamos los 12 SKUs que faltan. Pero hay dos puntos de la especificación que están causando daño y necesito que los veamos esta semana, no a fin de mes:

1. **Reintentos tras timeout crean Sales Orders duplicadas.** En 92 órdenes con `TIMEOUT` tenemos exactamente una SO por intento (#SO = #TIMEOUT + 1): el request que ustedes registran como fallido sí se completa en NetSuite, y el reintento a los 2 minutos crea otra. Hay 315 SO duplicadas en septiembre; una orden (`2000014732`) tiene 39. Los 429 no duplican; el timeout sí. Pido como **cambio de configuración, no evolutivo**: no reintentar en timeout (sólo en 429 y errores de conexión) hasta que el flujo tenga idempotencia. Del lado nuestro desplegamos hoy un control que rechaza la segunda SO del mismo `mp_order_id` con el error `DUPLICATE_MP_ORDER`: necesito que el iPaaS lo trate como "ya existe", no como fallo a reintentar.
2. **`ITEM_NOT_FOUND` se reintenta 3 veces y se descarta en silencio.** 160 órdenes entregadas no existen en NetSuite y nadie en Andina se enteró en 26 días. Pido el *replay* de esas 160 (lista adjunta) una vez cargado el mapeo, y que las órdenes que no se pueden crear queden en una cola visible para nosotros con alerta, en lugar de descartarse.

Para la idempotencia real (`externalId = mp_order_id`, consultar antes de reintentar, backoff y respeto del `Retry-After`) sí acepto que es evolutivo: mándenme la cotización y lo priorizamos para después del evento. También quiero revisar juntos por qué una SO tarda más de 120 s en las ventanas 22–01 h; de nuestro lado estoy mirando qué corre sincrónico al crear la orden y la concurrencia con otros procesos. Eso probablemente baje tanto los timeouts como los 429.

Gracias, y avisame hoy si el cambio de reintentos y el replay se pueden hacer con el equipo que tienen disponible.
