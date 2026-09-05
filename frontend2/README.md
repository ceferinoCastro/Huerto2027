# frontend2 — Administración del Huerto Vivo

Aplicación administrativa independiente en HTML, CSS y JavaScript puro.

Incluye cuatro secciones:

- asociaciones entre sensores y variables educativas;
- mediciones manuales diarias de altura para 20 plantas por huerto, con
  promedio instantáneo y gráfico de los últimos 30 días.
- importación de archivos CSV del datalogger Hanna HI981420.
- campañas simplificadas del huerto, compatibles con los documentos históricos
  de la colección `campania`.

## Ejecutar

Con FastAPI activo en `http://127.0.0.1:8000`:

~~~bash
cd frontend2
python3 servidor.py
~~~

Abrir `http://localhost:5600/`.

`servidor.py` sirve los archivos estáticos y reenvía `/api/*` a FastAPI para
evitar CORS sin modificar el backend.

Los endpoints de asociaciones todavía no existen. Consulta
`ENDPOINTS_REQUERIDOS.md` para el contrato esperado. Mientras FastAPI responda
404, la interfaz permite explorar sensores y variables, pero deshabilita crear,
editar y eliminar para no simular persistencia.

## Mediciones de plantas

El backend utiliza la colección independiente `mediciones_plantas`; no mezcla
estos registros con `lecturas`.

Endpoints:

- `GET /api/v1/mediciones-plantas?localidad=pica&fecha=2026-09-02`
- `POST /api/v1/mediciones-plantas`
- `GET /api/v1/mediciones-plantas/promedio?localidad=pica&dias=30`

Para crear o verificar los índices de la colección:

~~~bash
cd backend
.venv/bin/python -m scripts.create_mediciones_plantas_indexes
~~~

El formulario acepta plantas completamente vacías y solo envía las realmente
medidas. Cada planta enviada requiere únicamente un `altura_cm` positivo. Al
cambiar localidad o fecha, el GET diario rellena las alturas existentes.
Guardar nuevamente la misma localidad, ciclo, fecha y planta actualiza el
registro en vez de duplicarlo.

El gráfico consulta siempre `GET /api/v1/mediciones-plantas/promedio` para la
localidad seleccionada, usa únicamente alturas positivas y vuelve a cargarse
después de cada guardado. No muestra datos simulados cuando el huerto está vacío.

## Archivos Hanna

La pestaña **Cargar CSV Hanna** envía el archivo original al backend mediante
`multipart/form-data`. FastAPI detecta metadatos y la tabla, elimina caracteres
nulos, convierte fechas y decimales, clasifica registros sospechosos y guarda
todo en la colección independiente `mediciones_hanna`.

Endpoints:

- `POST /api/v1/mediciones-hanna/importar-csv`
- `GET /api/v1/mediciones-hanna/resumen?localidad=pica`

Para crear o verificar sus índices:

~~~bash
cd backend
.venv/bin/python -m scripts.create_mediciones_hanna_indexes
~~~

La clave histórica era `localidad + equipo_serial + datetime_local`.

La administración nueva mantiene las asociaciones permanentes en
`dataloggers_hanna`, separada de los equipos Zentra. Antes de importar se lee el
modelo, serial e Instrument ID. Las mediciones nuevas conservan tanto
`serial_hanna` como el alias histórico `equipo_serial`, y la deduplicación usa
`serial_hanna + datetime_local`. Los documentos antiguos siguen siendo
consultables mediante `equipo_serial`.

Endpoints de equipos:

- `GET /api/v1/dataloggers-hanna`
- `POST /api/v1/dataloggers-hanna/asociar`
- `PUT /api/v1/dataloggers-hanna/{serial}/corregir-asignacion`
- `POST /api/v1/dataloggers-hanna/{serial}/reemplazar`
- `POST /api/v1/mediciones-hanna/analizar-csv`

Los índices pueden prepararse manualmente con:

~~~bash
cd backend
.venv/bin/python -m scripts.create_hanna_datalogger_indexes
~~~

## Campañas del huerto

Las campañas nuevas se guardan en la colección existente `campania`. El
backend expone el modelo simplificado y centraliza estos aliases para conservar
compatibilidad: `cultivo/especie`, `fecha_siembra/desde` y
`fecha_cosecha_estimada/hasta`. No copia sensores, variables ni mediciones.

- `GET /api/v1/campanias?colegio_id=...`
- `GET /api/v1/campanias/activa?colegio_id=...`
- `POST /api/v1/campanias`
- `PUT /api/v1/campanias/{id}/finalizar`
- `PUT /api/v1/campanias/{id}/cancelar`

Los índices pueden prepararse manualmente con:

~~~bash
cd backend
.venv/bin/python -m scripts.create_campaign_indexes
~~~
