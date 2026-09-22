# Prompt — Rediseño de Carteles y Asociaciones (Huerto2027)

Usa este texto tal cual como instrucción para (re)iniciar el trabajo, en esta
sesión o en una nueva.

---

## Contexto

Proyecto "Huerto Escolar 2027", carpeta `~/Huerto2027` (repo git, rama `main`).
Estructura: `backend/` (FastAPI + MongoDB, base `agromonitor`), `frontend/`
(vista pública ilustrada para estudiantes, HTML/CSS/JS puro, puerto 5500) y
`frontend2/` (panel administrativo, HTML/CSS/JS puro, puerto 5600).

Existe un punto de retorno con el estado previo a este trabajo en
`~/Huerto2027/.return-points/carteles-asociaciones-rediseno-20260905-before/`
(copia de `backend/`, `frontend/` y `frontend2/`, con instrucciones de
restauración en `NOTA.md` dentro de esa carpeta). Si algo se rompe durante el
desarrollo, restaura desde ahí antes de seguir.

## Diagnóstico (ya confirmado en el código)

Hoy "cartel" (la variable educativa que se muestra a los estudiantes) no es
una entidad gestionable: existe duplicada y desincronizada en tres lugares:

1. `backend/app/services/sensor_associations.py` — tupla fija
   `EDUCATIONAL_VARIABLES` (11 registros: clave, nombre educativo, fuente,
   variable técnica, modelo de sensor, unidad, categoría). De ahí sale
   `educational_catalog()`, usado por `GET /localidades/{localidad}/variables-educativas/ultima`.
2. Colección Mongo `asociaciones-sensores` (modelo
   `backend/app/models/sensor_associations.py`) — además del vínculo técnico
   (sensor, variable técnica), duplica `nombre_educativo`, `unidad`,
   `categoria`, `orden`, `visible_frontend`. Es la única parte editable desde
   `frontend2` (formulario "Editar asociación"), pero sus cambios de nombre no
   se reflejan en la tabla "Configuración de carteles" de `frontend2/app.js`
   porque esa tabla pinta siempre `definition.nombre_educativo` (el catálogo
   fijo del punto 1), nunca `association.nombre_educativo` (ver
   `renderAsociaciones()`, línea ~110 de `frontend2/app.js`).
3. `frontend/js/catalogo-carteles.js` — segundo catálogo fijo, en JS, con 11
   entradas propias (`SENSOR_CARD_CATALOG`): posición x/y sobre la imagen
   ilustrada del huerto, ícono, texto explicativo, ruta de conexión visual y,
   en dos casos, una "regla" de medición. El nombre que ven los estudiantes
   sale de aquí (`item.label`), totalmente independiente de los otros dos.

No hay ningún CRUD para crear o eliminar un cartel; solo se pueden editar
asociaciones sobre las 11 claves ya fijas en el código.

## Objetivo del rediseño

Separar dos conceptos que hoy están mezclados:

- **Cartel educativo**: la definición de "qué se muestra" — código/clave
  único, nombre educativo, categoría, unidad, orden, visibilidad. Debe poder
  crearse, editarse y eliminarse desde `frontend2`, con una única fuente de
  verdad en la base de datos.
- **Asociación cartel ↔ variable técnica**: el vínculo "de dónde sale el
  dato" — sensor Zentra, equipo Hanna, o medición manual. Referencia a un
  cartel existente por su clave; no debe volver a guardar nombre, unidad,
  categoría ni orden (esos viven solo en el cartel).

## Cambios a implementar

### 1. Backend — nueva colección y modelo de "Cartel"

- Nueva colección Mongo, p. ej. `carteles_educativos`, con documentos:
  `clave` (string único), `nombre_educativo`, `categoria`, `unidad`, `orden`,
  `visible_frontend`, `fuente_esperada` (zentra/hanna/manual, informativo),
  `variable_tecnica_esperada` (opcional, para sugerir en el formulario de
  asociación), `created_at`/`updated_at`.
- Migrar los 11 registros de `EDUCATIONAL_VARIABLES` como semilla inicial
  (script en `backend/scripts/`, siguiendo el patrón de los scripts
  `create_*_indexes.py` existentes) — no perder ningún dato: mapear
  clave→nombre_educativo→fuente→variable_tecnica→modelo→unidad→categoria tal
  como están hoy.
- Modelo Pydantic `CartelInput`/`CartelDocument` en
  `backend/app/models/` (nuevo archivo, p. ej. `carteles.py`), con
  validaciones equivalentes a las que ya existen en
  `SensorAssociationInput` (longitudes, `orden` entre 0 y 1000, etc.).
- Endpoints CRUD en `backend/app/api/routes/carteles.py`, prefijo
  `/api/v1/carteles`:
  - `GET /api/v1/carteles` — lista todos, ordenados por `orden`.
  - `POST /api/v1/carteles` — crea uno nuevo (clave única).
  - `PUT /api/v1/carteles/{clave}` — edita nombre/categoria/unidad/orden/visibilidad.
  - `DELETE /api/v1/carteles/{clave}` — elimina, mostrando error claro si aún
    tiene asociaciones activas apuntando a esa clave (evitar huérfanos; o
    permitirlo y dejar la asociación sin cartel, a decidir según lo que sea
    más simple de mantener).
  - Seguir el mismo patrón de manejo de errores que
    `backend/app/api/routes/sensor_associations.py` (`_domain_error`,
    `DomainConflictError`, `DomainNotFoundError`).
- Registrar el router en `backend/app/main.py` igual que los demás
  (`application.include_router(carteles_router, prefix=app_settings.api_v1_prefix)`).

### 2. Backend — adelgazar el modelo de asociación

- En `backend/app/models/sensor_associations.py`, quitar de
  `SensorAssociationInput` los campos `nombre_educativo`, `unidad`,
  `categoria`, `orden` (siguen existiendo solo en el cartel). Mantener
  `clave_educativa` (ahora debe existir como cartel válido — agregar
  validación que lo compruebe contra la colección de carteles),
  `sensor_sn`, `sensor_name`, `variable_tecnica`, `ubicacion`,
  `profundidad_cm`, `source`, `visible_frontend` (o mover también
  `visible_frontend` al cartel, si se decide que la visibilidad es propiedad
  del cartel y no de la asociación — recomendado, para que "ocultar" no
  dependa de tener o no una asociación activa).
- Actualizar `backend/app/db/mongodb.py` (métodos
  `create_sensor_association`, `update_sensor_association`,
  `list_sensor_associations`, etc.) para no depender de los campos
  eliminados.

### 3. Backend — leer el catálogo desde la base de datos

- `educational_catalog()` en `backend/app/services/educational_measurements.py`
  debe consultar la colección `carteles_educativos` en vez de recorrer la
  tupla `EDUCATIONAL_VARIABLES`. Mantener `EDUCATIONAL_VARIABLES` solo como
  constante de semilla para el script de migración, o eliminarla una vez
  migrada.
- `GET /localidades/{localidad}/variables-educativas/ultima`
  (`latest_educational_summary` en `backend/app/api/routes/educational_measurements.py`)
  debe iterar sobre los carteles definidos en base de datos (ya no sobre
  `EDUCATIONAL_NAMES` fijo + apéndice de asociaciones sueltas) para que un
  cartel nuevo aparezca automáticamente sin tocar código.
- Revisar `technical_detail()`, `empty_measurement()` y `public_measurement()`
  en el mismo archivo de servicios: deben resolver `nombre`/`unidad`/
  `categoria` siempre desde el cartel (vía `association` o consultando el
  cartel directamente si no hay asociación), nunca desde una constante fija.

### 4. Frontend2 — separar la UI en dos secciones

- Nueva sección "Carteles" (tabla + formulario) para crear, editar y
  eliminar carteles: clave, nombre educativo, categoría, unidad, orden,
  visible. Usar el mismo patrón de `api.js`/`app.js` ya existente (agregar
  `fetchCarteles`, `crearCartel`, `actualizarCartel`, `eliminarCartel` en
  `frontend2/api.js`).
- El formulario "Editar asociación" (`frontend2/app.js`,
  `payloadFormulario()`, `editar()`, `prepararAsociacion()`) se simplifica:
  en vez de permitir editar `nombre_educativo`/`unidad`/`categoria`/`orden`,
  pasa a elegir un cartel ya existente (select) y solo completa el vínculo
  técnico (sensor, variable técnica, ubicación, profundidad).
- La tabla "Configuración de carteles" (`renderAsociaciones()`, línea ~110)
  debe pintar el nombre desde el cartel (que ahora es la única fuente),
  eliminando la ambigüedad actual entre `definition.nombre_educativo` y
  `association.nombre_educativo`.
- Actualizar `frontend2/README.md` y `frontend2/ENDPOINTS_REQUERIDOS.md` con
  el contrato nuevo (o borrar `ENDPOINTS_REQUERIDOS.md` si ya no aplica,
  dado que en teoría los endpoints de asociaciones ya existen — confirmar
  contra el backend actual antes de borrar nada).

### 5. Frontend público — fase separada, más delicada

`frontend/js/catalogo-carteles.js` (`SENSOR_CARD_CATALOG`) define posición,
ícono, ruta de conexión y regla de medición por cada cartel — metadata
visual que hoy no existe en ningún otro lado. Para esta primera etapa **no
es necesario** tocar este archivo: basta con que el nombre mostrado
(`item.label`) dependa de la clave, y que un cartel nuevo sin posición
asignada simplemente no aparezca en la vista ilustrada (documentar esta
limitación). Si más adelante se quiere que carteles nuevos aparezcan aquí
también, se deberá extender el modelo de "Cartel" con posición/ícono/ruta
opcionales y generar este catálogo dinámicamente — dejarlo para una
iteración futura, no mezclarlo con este trabajo.

## Pruebas y verificación

- Backend tiene tests en `backend/tests/` (`test_sensor_associations.py`,
  `test_frontend2_structure.py`, `test_frontend2_api_runtime.py`, etc.) —
  revisar cuáles cubren el modelo/endpoints tocados y actualizarlos; agregar
  tests nuevos para el CRUD de carteles (crear, editar, eliminar, eliminar
  con asociaciones activas, catálogo dinámico en `/ultima`).
- Verificar manualmente en `frontend2` (puerto 5600): crear un cartel nuevo,
  asociarlo a un sensor, confirmar que aparece en la tabla con el nombre
  correcto, editarlo y confirmar que el cambio se refleja de inmediato sin
  recargar código, eliminarlo y confirmar que desaparece.
- Confirmar que `frontend` (puerto 5500) sigue funcionando igual para los 11
  carteles existentes (no debe romperse nada de lo actual).

## Alcance sugerido por etapas

1. Backend: colección + modelo + CRUD de carteles, migración de semilla.
2. Backend: adelgazar asociación, actualizar `/ultima` y servicios relacionados.
3. Frontend2: sección de carteles + formulario de asociación simplificado + tabla corregida.
4. Pruebas backend actualizadas/nuevas.
5. (Opcional, fase futura) Frontend público dinámico.

Antes de tocar código, confirmar conmigo si `visible_frontend` debe vivir en
el cartel o seguir en la asociación, y si al eliminar un cartel con
asociaciones activas se debe bloquear o eliminar en cascada.
