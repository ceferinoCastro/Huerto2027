# Prompt — Catálogo visual dinámico para el frontend público (fase 2 del rediseño de carteles)

## Contexto

Ya está en producción la fase 1 del rediseño: los 11 carteles educativos
viven en la colección Mongo `carteles_educativos` y se gestionan desde
`frontend2` (crear/editar/eliminar, con nombre/unidad/categoría/orden/
visibilidad). El frontend público (`frontend/`, puerto 5500 — la vista
ilustrada para estudiantes) sigue sin usar esa base de datos: dibuja los
carteles a partir de un array fijo en código,
`frontend/js/catalogo-carteles.js` (`SENSOR_CARD_CATALOG`), que además de
`label`/`unit`/`source` (que ya duplican datos del cartel en Mongo) trae
metadata puramente visual que hoy no existe en ningún otro lado: posición
x/y sobre la imagen del huerto, el punto de destino al que apunta la línea
de conexión, los puntos intermedios de esa línea (curva), el ícono, el
ancla del texto, y en dos casos (`altura_planta`, `largo_raiz`) una "regla"
de medición dibujada sobre la escena.

Existe un punto de retorno con el estado previo a esta fase en
`~/Huerto2027/.return-points/catalogo-visual-dinamico-20260905-before/`
(instrucciones de restauración en su `NOTA.md`). Esta fase toca directamente
lo que ven los estudiantes — probar con calma antes de dar por cerrado.

## Decisiones ya tomadas (no las cambies sin confirmar)

1. Los 11 carteles existentes **mantienen exactamente su posición y línea de
   conexión actuales** — se migran tal cual están hoy en
   `frontend/js/catalogo-carteles.js` (los valores de este archivo, no los
   de una versión anterior en git — este archivo tiene ajustes manuales
   recientes sin commitear que son los que hay que preservar).
2. Un cartel **nuevo** (creado desde frontend2 sin datos visuales) **no
   aparece en la escena ilustrada** hasta que alguien le cargue posición y
   destino desde el formulario de carteles. No se construye ninguna lista
   genérica alternativa para carteles sin posición — simplemente no se
   dibujan todavía.
3. La edición de posición/línea de conexión se hace con **campos numéricos**
   en el formulario de `frontend2` (x, y, etc.), no con un editor visual de
   arrastrar-y-soltar — eso queda para un proyecto aparte si se necesita
   más adelante.

## Datos visuales a agregar al modelo de Cartel

Agregar estos campos **opcionales** (todos `None`/vacíos por defecto, para
no romper carteles existentes que aún no los tengan) a
`backend/app/models/carteles.py` (`CartelInput`) y a la colección
`carteles_educativos`:

- `icono: str | None` — uno de un set fijo ya usado en
  `frontend/js/app.js` (objeto `iconosCartel`): `temperature`, `humidity`,
  `leaf-water`, `temperature-soil`, `temperature-depth`, `soil-water`,
  `ph-water`, `salts-water`, `temperature-water`, `plant-height`,
  `root-length`. Agregar además un ícono genérico (`generic` o similar,
  con un SVG simple) para carteles nuevos que no calcen con ninguno de los
  existentes.
- `grupo_visual: str | None` — uno de `air`, `plant`, `earth`, `water`
  (las claves de `SENSOR_GROUP_CATALOG`, que se mantiene como constante fija
  en `catalogo-carteles.js` — son 4 temas visuales con color, no cambian
  por cartel).
- `compartir_conexion_con: str | None` — equivalente a `sharedTarget`: id
  arbitrario para agrupar varios carteles que apuntan al mismo punto de la
  escena (hoy `"atmosphere"` para los dos de aire, `"pond"` para los tres
  de agua). Vacío = no comparte destino con nadie más.
- `mostrar_conexion: bool` (default `true`) — equivalente a `showConnection`.
- `posicion_x: float | None`, `posicion_y: float | None` — posición del
  cartel sobre la imagen, en porcentaje (equivalente a
  `position.desktop.x/y`). El orden de apilamiento en mobile
  (`position.mobile.order`) puede resolverse reutilizando el campo `orden`
  que el cartel ya tiene — no crear un campo aparte para eso.
- `destino_x: float | None`, `destino_y: float | None`,
  `destino_zona: str | None` — el punto de la escena al que apunta la línea
  y su descripción accesible (equivalente a `target.{x,y,zone}`).
- `ruta_punto1_x/y: float | None`, `ruta_punto2_x/y: float | None` — hasta
  dos puntos de control para la curva de conexión (equivalente al array
  `route`, que en los datos actuales nunca tiene más de 2 elementos — por
  eso alcanza con dos pares de campos en vez de un array dinámico).
- `ancla: str | None` — uno de `top`, `bottom`, `left`, `right`
  (equivalente a `anchor`).
- `etiqueta_corta: str | None` — texto corto para vista mobile
  (`shortLabel`); si está vacío, el frontend usa `nombre_educativo` completo.
- `explicacion: str | None` — el texto educativo que hoy vive fijo en
  `explanation` de cada entrada de `SENSOR_CARD_CATALOG`; pasa a ser un
  campo editable del cartel, igual que `nombre_educativo`.
- `regla: dict | None` — la configuración de "regla de medición" que hoy
  solo usan `altura_planta` y `largo_raiz` (`{id, label, x, y1, y2,
  tickSide}`). **No exponer este campo en el formulario de frontend2 por
  ahora** (es una función muy específica de solo 2 carteles) — pero
  preservarlo intacto en cualquier edición, con el mismo patrón ya aplicado
  para `fuente_sugerida`/`variable_tecnica_sugerida`/`sensor_modelo_sugerido`
  (capturar el valor existente al entrar en modo edición y reenviarlo sin
  cambios en el payload, para no repetir el bug que se corrigió hace poco).

## Migración de los 11 carteles existentes

Extender (o crear un script nuevo junto a) `migrate_educational_posters.py`
para poblar estos campos visuales en los 11 carteles ya existentes en Mongo,
usando exactamente los valores actuales de
`frontend/js/catalogo-carteles.js` (el archivo tal como está en el
working tree ahora mismo, con sus ediciones manuales sin commitear). Debe
ser idempotente: si un cartel ya tiene datos visuales cargados, no
sobrescribirlos sin `--force`. Mapeo campo a campo:

- `label` → ya existe como `nombre_educativo`, no migrar de nuevo (evitar
  pisar ediciones ya hechas desde frontend2).
- `explanation` → `explicacion`
- `shortLabel` → `etiqueta_corta`
- `icon` → `icono`
- `group` → `grupo_visual`
- `sharedTarget` → `compartir_conexion_con`
- `showConnection` → `mostrar_conexion`
- `position.desktop.x` → `posicion_x`, `position.desktop.y` → `posicion_y`
- `target.x/y/zone` → `destino_x`/`destino_y`/`destino_zona`
- `route[0]` → `ruta_punto1_x/y` (si existe), `route[1]` →
  `ruta_punto2_x/y` (si existe)
- `anchor` → `ancla`
- `ruler` (si existe, solo `altura_planta` y `largo_raiz`) → `regla`
  (guardar el objeto tal cual)

## Backend — exponer los datos

`GET /api/v1/carteles` ya devuelve el documento completo de cada cartel
(via `serialize_mongo`), así que no hace falta un endpoint nuevo — alcanza
con que el documento tenga estos campos. Confirmar que la validación de
Pydantic no rompa documentos existentes sin estos campos (deben ser
opcionales de verdad, no solo con default en el constructor).

## Frontend2 — formulario de carteles

Agregar una sección "Datos visuales (avanzado)" — puede ir colapsada por
defecto para no abrumar el flujo normal de crear/editar nombre y unidad —
con los campos numéricos/select correspondientes a todo lo de arriba
excepto `regla`. Aplicar el mismo cuidado que en el fix anterior: al entrar
en modo edición, cargar los valores actuales de estos campos en el estado
del formulario (no solo los que tengan input visible), y al construir el
payload del `PUT`, incluir siempre `regla` tal cual estaba (capturado, no
editado) para no perderla.

## Frontend público — catálogo dinámico

`frontend/js/catalogo-carteles.js`: `SENSOR_CARD_CATALOG` deja de ser un
array estático. En su lugar, exportar una función async (por ejemplo
`cargarCatalogoVisual()`) que haga `fetch` a `/api/v1/carteles`, filtre a
los carteles con `posicion_x`, `posicion_y`, `destino_x` y `destino_y`
definidos (los que no los tengan quedan fuera de la escena, según lo
decidido arriba), y arme para cada uno un objeto con la misma forma que
antes (`key`, `label`, `explanation`, `shortLabel`, `icon`, `unit`,
`source`, `group`, `sharedTarget`, `showConnection`, `position`, `target`,
`route`, `anchor`, y `ruler` si viene presente) — mapeando los nombres de
campo de vuelta (`clave_educativa`→`key`, `nombre_educativo`→`label`,
`explicacion`→`explanation`, etc.), para que el resto del código de
`frontend/js/app.js` (que dibuja tarjetas, líneas de conexión, reglas, el
panel de detalle, etc.) no tenga que reescribirse — solo cambia de dónde
sale el array. `SENSOR_GROUP_CATALOG` y `BACKGROUND_CROP` se mantienen como
constantes fijas, sin cambios.

`frontend/js/app.js`: hoy al final del archivo se llama de forma síncrona
`crearCartelesVisuales(); dashboard=estadoInicial(); actualizar(); cargar();`
usando el `SENSOR_CARD_CATALOG` importado como constante fija. Hay que
convertir el arranque en una secuencia async que primero espera
`cargarCatalogoVisual()` y solo después llama a `crearCartelesVisuales()` y
al resto — revisar todos los usos de `SENSOR_CARD_CATALOG`/
`SENSOR_GROUP_CATALOG` en este archivo (se usan en varias funciones:
`crearCartelesVisuales`, `seleccionarVariableEducativa`,
`renderSelectedVariableDetail`, `actualizarCarteles`, etc.) y asegurarse de
que todas usen el catálogo ya cargado (por ejemplo, guardándolo en una
variable de módulo `let sensorCardCatalog = []` que se llena una sola vez al
arrancar, en vez de la constante importada).

Manejo de errores: si la llamada a `/api/v1/carteles` falla (backend caído),
mostrar la escena sin carteles en vez de romper la página — reusar el
patrón de degradación que ya existe en `cargar()` para el resto del
dashboard (mostrar un estado "no disponible" en vez de una pantalla en
blanco).

## Tests a revisar

`backend/tests/test_frontend_stage2_visualization.py` prueba hoy
directamente los valores fijos de `SENSOR_CARD_CATALOG` como array
estático — una vez que ese catálogo se arma dinámicamente desde la API, la
mayoría de esos tests dejan de tener sentido tal como están escritos.
Reemplazarlos por tests que verifiquen: (a) que `cargarCatalogoVisual()`
filtra correctamente los carteles sin posición completa, y (b) que el
mapeo de campos es correcto para un cartel de ejemplo con todos los campos
visuales cargados. No dejar tests rotos ni tests que ya no prueban nada
real.

## Verificación manual

1. Con los 11 carteles migrados, abrir `frontend` (puerto 5500) y confirmar
   visualmente que la escena ilustrada se ve exactamente igual que antes
   (mismas posiciones, mismas líneas, mismos íconos) — ningún cambio
   perceptible para un estudiante.
2. Crear un cartel de prueba nuevo desde `frontend2` sin datos visuales y
   confirmar que NO aparece en la escena de `frontend`.
3. Editarlo agregando posición y destino, y confirmar que SÍ aparece,
   correctamente ubicado.
4. Editar el nombre de un cartel existente (por ejemplo
   `temperatura_aire`) y confirmar que el label de la tarjeta ilustrada en
   `frontend` cambia también (esto era justamente el objetivo original del
   rediseño, ahora extendido al frontend público).
5. Confirmar que los carteles con "regla" (`altura_planta`, `largo_raiz`)
   siguen dibujando su regla de medición correctamente tras la migración.
