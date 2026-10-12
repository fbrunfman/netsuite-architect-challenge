# Uso de IA

Usé **Claude (Anthropic) desde Claude Code**, con acceso directo a la carpeta del repo, como par de trabajo durante todo el challenge.

## Qué hizo la IA

- **Caso 1.** Leyó el código, los objetos SDF y los CSV; escribió el script de análisis (`caso-1/analisis/analisis_caso1.py`) que cruza recepciones, landed costs, líneas, maestro de pedimentos y CFDI; propuso las tres causas; escribió el módulo de reglas compartido, la refactorización de los dos User Events, los cambios en los XML de deployment y los 24 tests nuevos (incluido el *replay* de los 48 Item Receipts contra el gate). Verificó que los tests nuevos fallan contra el código original (16 de 37) y pasan con el corregido. Redactó la nota.
- **Caso 2.** Escribió el script de análisis (`caso-2/analisis/analisis_caso2.py`) sobre los 8 CSV, separó y cuantificó las causas (duplicados por timeout, SKU sin mapear, TO parciales, líneas sin re-comprometer, diferencias de stock en el FC) y redactó diagnóstico, plan y respuestas a los stakeholders.
- **Caso 3.** Propuso el diseño del proceso, generó el diagrama de swimlanes como SVG con un script propio (`caso-3/analisis/diagrama_gen.py`), y redactó la matriz de datos.

## Qué hice yo

- Definí el alcance y el orden, revisé cada hallazgo contra los datos y el código, y corregí o descarté lo que no me cerraba.
- Puntos donde **mi criterio de NetSuite** pesa más que lo que la IA puede verificar desde el repo, y que asumo como propios: que el job *Receive Inbound Shipment* corre en un contexto de ejecución que no estaba en la lista del deployment (es la hipótesis más consistente con los datos: 4 de 4 recepciones malas vienen del job; se confirma en sandbox con `runtime.executionContext` en el log); que un reintento tras *read timeout* duplica Sales Orders cuando no hay `externalId` (lo demuestra el log: #SO = #TIMEOUT + 1 en las 92 órdenes); la estrategia de lote (lote de fabricación para regulados, pedimento vía maestro) y los supuestos fiscales/regulatorios por país marcados como tales en el caso 3.

## Qué no usé la IA para

No ejecutó nada contra una cuenta de NetSuite ni tuvo acceso a datos reales de ningún cliente; todo corrió sobre los CSV sintéticos y el proyecto SDF del repo.
