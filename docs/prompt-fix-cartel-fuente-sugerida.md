# Prompt — Corregir pérdida de `fuente_sugerida` al editar un cartel

## Bug encontrado (verificado manualmente en frontend2, puerto 5600)

Al editar un cartel ya existente desde la pestaña "Carteles educativos" —
por ejemplo, solo cambiar el `nombre_educativo` de "Temperatura del aire" a
"Temperatura Atmosférica"— el cartel pierde sus campos
`fuente_sugerida`, `variable_tecnica_sugerida` y `sensor_modelo_sugerido`
(quedan en `null` después del `PUT`).

Confirmado con `GET /api/v1/carteles` antes/después de la edición: los tres
campos existían con valores correctos ("zentra", "Air Temperature",
"ATMOS 14") y quedaron en `null` tras guardar la edición.

## Causa

El formulario "Editar cartel" en `frontend2/index.html` / `frontend2/app.js`
solo expone `clave_educativa`, `nombre_educativo`, `unidad`, `categoria`,
`orden` y `visible_frontend`. Al construir el payload del `PUT
/api/v1/carteles/{clave}`, los campos `fuente_sugerida`,
`variable_tecnica_sugerida` y `sensor_modelo_sugerido` no se incluyen (o se
envían como `null`), y como `CartelInput`/`update_cartel` en el backend
hacen un reemplazo completo del documento (no un merge parcial), esos
valores se pierden aunque el usuario no haya tocado esos campos.

## Impacto real (verificado)

No hay pérdida de datos de asociación: la asociación real en
`asociaciones_sensores` no se toca al editar un cartel, y el endpoint
`/localidades/{localidad}/variables-educativas/ultima` sigue devolviendo el
dato real correctamente (porque para `source != "hanna"` resuelve por
`sensor_association()`, que no depende de `fuente_sugerida`).

El problema es en la tabla "Configuración de carteles" de `frontend2`
(`renderAsociaciones()` en `app.js`): esa tabla decide cómo pintar cada fila
—como Zentra, Hanna o "manual"— usando `definition.fuente` (que viene del
campo `fuente_sugerida` del cartel, expuesto en `catalogo` por
`educational_catalog()`). Con `fuente_sugerida = null`, la fila cae en la
rama "manual" por defecto: pierde los botones "Editar"/"Eliminar
asociación" y en su lugar muestra "Ver mediciones" como si fuera una
medición manual de planta, ocultando el manejo de la asociación Zentra/Hanna
real que sigue existiendo. Es un bug de UI/gestión, no de integridad de
datos, pero bloquea la administración normal de ese cartel hasta que se
corrija.

Ya se aplicó un `PUT` manual para reponer los valores de `temperatura_aire`
(`fuente_sugerida: "zentra"`, `variable_tecnica_sugerida: "Air Temperature"`,
`sensor_modelo_sugerido: "ATMOS 14"`), así que ese cartel puntual ya quedó
bien. El bug de fondo sigue sin corregirse: **cualquier otra edición de
cartel repetirá el problema**.

## Corrección a implementar

Elegir una de estas dos soluciones (la primera es más simple y consistente
con el resto del código):

**Opción A — Preservar los campos "sugeridos" al editar (recomendada)**

En `frontend2/app.js`, en la función que abre el modo edición del cartel
(donde hoy se precargan `clave-educativa`, `nombre-educativo`, `unidad`,
`categoria`, `orden`, `visible`), guardar también en el estado del formulario
(por ejemplo en variables ocultas o en `cartelState.editando`) los valores
actuales de `fuente_sugerida`, `variable_tecnica_sugerida` y
`sensor_modelo_sugerido` del cartel que se está editando. Al construir el
payload del `PUT` (la función equivalente a `payloadFormulario()` pero para
carteles), incluir esos tres valores tal cual estaban, en vez de omitirlos
u omitir el objeto entero. No hace falta exponerlos como campos editables en
el formulario visible — son solo metadata para prellenar el formulario de
asociación, así que basta con no perderlos silenciosamente.

**Opción B — Volver el PUT de carteles parcial (merge) en el backend**

Cambiar `CartelInput` (o crear un `CartelPatchInput` con todos los campos
opcionales) y `update_cartel` en `backend/app/db/mongodb.py` para que el
`PUT /api/v1/carteles/{clave}` haga `$set` solo de los campos presentes en
el payload, dejando intactos los que no se envíen. Esto es más robusto a
futuros formularios incompletos, pero cambia la semántica de "PUT" (deja de
ser un reemplazo completo) — revisar que no rompa la validación de
Pydantic (que hoy exige todos los campos requeridos).

## Verificación después de corregir

1. Editar cualquiera de los 11 carteles existentes (por ejemplo, solo el
   `orden` o solo el `nombre_educativo`).
2. Confirmar con `GET /api/v1/carteles` que `fuente_sugerida`,
   `variable_tecnica_sugerida` y `sensor_modelo_sugerido` de ese cartel
   siguen siendo los mismos que antes de la edición.
3. Confirmar en la pestaña "Asociaciones sensores" de `frontend2` que la
   fila correspondiente en "Configuración de carteles" sigue mostrando
   correctamente su fuente real (Zentra/Hanna/Manual) y sus botones de
   acción (Editar/Eliminar asociación, o Ver equipo Hanna, según
   corresponda), sin caer en la rama "manual" por error.
4. Agregar un test de regresión en `backend/tests/test_carteles.py` que
   edite un cartel cambiando solo `nombre_educativo` y verifique que
   `fuente_sugerida`/`variable_tecnica_sugerida`/`sensor_modelo_sugerido`
   no cambian.
