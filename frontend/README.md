# Huerto Vivo Escolar — frontend independiente

Frontend en HTML, CSS y JavaScript puro. No requiere React, Vinext, npm ni Node.

## Ejecutar

Desde la carpeta frontend:

~~~bash
python3 servidor.py
~~~

Abrir http://localhost:5500.

## Conectar FastAPI

Editar js/configuracion.js. El frontend consulta las variables educativas a
través de sus asociaciones:

~~~text
GET /api/v1/localidades/{localidad}/variables-educativas/ultima
GET /api/v1/localidades/{localidad}/variables-educativas/{variable}/historial
~~~

El servidor local reenvía las consultas `/api/*` a FastAPI para evitar CORS sin
modificar el backend. Si FastAPI no responde, la interfaz muestra el estado
`No disponible`; no sustituye la consulta por valores demostrativos.

La tarjeta **CRECIMIENTO** resuelve primero la asociación manual y consulta el
promedio real de alturas registrado desde `frontend2`. Si no hay mediciones,
muestra el estado vacío.
