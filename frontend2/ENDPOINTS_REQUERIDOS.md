# API pendiente para asociaciones de sensores

El backend actual no expone `/api/v1/asociaciones-sensores` ni
`/api/v1/dataloggers`. La interfaz detecta esta situación mediante HTTP 404 y
deshabilita las operaciones de escritura.

## Modelo sugerido

~~~json
{
  "localidad": "pica",
  "colegio_id": "681809ad4380729348f49162",
  "device_sn": "z6-29235",
  "clave_educativa": "temperatura_tierra",
  "nombre_educativo": "Temperatura de la tierra",
  "sensor_sn": "T12-00015180",
  "variable_tecnica": "Soil Temperature",
  "unidad": "°C",
  "categoria": "temperatura",
  "ubicacion": "Cama de cultivo 1",
  "profundidad_cm": 15,
  "visible_frontend": true,
  "orden": 1
}
~~~

## Endpoints requeridos

- `GET /api/v1/asociaciones-sensores?localidad={localidad}`
  - Respuesta: `{"status":"ok","count":0,"items":[]}`.
- `POST /api/v1/asociaciones-sensores`
  - Recibe el modelo sin `_id`; devuelve el registro creado con `_id`.
- `PUT /api/v1/asociaciones-sensores/{id}`
  - Recibe el modelo completo; devuelve el registro actualizado.
- `DELETE /api/v1/asociaciones-sensores/{id}`
  - Devuelve `{"status":"ok","deleted":true}`.

Validaciones recomendadas: localidad soportada; unicidad por
`localidad + clave_educativa`; existencia de `sensor_sn`; tipos y rangos para
`profundidad_cm` y `orden`; y rechazo de campos desconocidos.

La colección de asociaciones debe ser independiente de `lecturas`. Ninguna de
estas operaciones debe actualizar o eliminar documentos de `lecturas`.
