# Prompt — Migrar los 11 carteles educativos existentes a MongoDB

## Contexto

Proyecto Huerto2027 (`~/Huerto2027`). El backend ya tiene implementado el CRUD
de carteles (colección Mongo `carteles_educativos`, rutas `/api/v1/carteles`),
y `frontend2` ya muestra la pestaña "Carteles educativos" funcionando. Falta
un solo paso para cerrar el rediseño: cargar en la base de datos real
(MongoDB Atlas — ver `MONGODB_URI` en `backend/.env`) los 11 carteles que hoy
siguen definidos como semilla en código, en
`backend/app/services/sensor_associations.py` (constante
`EDUCATIONAL_POSTER_SEED`), para que pasen a vivir en la colección
`carteles_educativos` y dejen de depender del código fuente.

Ya existe un script idempotente para esto: `backend/scripts/migrate_educational_posters.py`.
No crea duplicados (compara contra lo que ya exista en la colección por
`clave_educativa`) y no sobrescribe carteles que ya se hayan creado o editado
manualmente desde `frontend2`.

**Importante:** este script debe ejecutarse desde una Terminal normal en la
Mac (no desde un entorno sandbox sin salida de red completa), porque necesita
conectarse por el protocolo nativo de Mongo (puerto 27017 + resolución SRV)
al cluster real en Atlas — una conexión que los entornos de ejecución
restringidos (por ejemplo, contenedores en la nube o VMs aisladas de
automatización) normalmente bloquean.

## Pasos a ejecutar

1. Ir a la carpeta del backend y usar su entorno virtual:

   ```bash
   cd ~/Huerto2027/backend
   ```

2. Ejecutar primero en modo dry-run (no escribe nada en la base de datos,
   solo imprime un reporte):

   ```bash
   .venv/bin/python scripts/migrate_educational_posters.py
   ```

   Verificar que el reporte liste los 11 carteles esperados —
   `temperatura_aire`, `humedad_aire`, `humedad_hojas`, `temperatura_tierra`,
   `temperatura_bajo_tierra`, `humedad_tierra`, `ph_agua`, `sales_agua`,
   `temperatura_agua`, `altura_planta`, `largo_raiz` — y que el resumen final
   diga "11 nuevos; 0 ya existentes" (o el número que corresponda si alguno
   ya se había creado a mano desde `frontend2`).

3. Si el reporte se ve correcto, aplicar de verdad:

   ```bash
   .venv/bin/python scripts/migrate_educational_posters.py --apply
   ```

   Debe confirmar algo como "Aplicación: 11 carteles creados." (o el número
   que corresponda).

4. Verificar en `frontend2` (con el backend —`uvicorn app.main:app --reload`—
   y `frontend2/servidor.py` corriendo) que la pestaña "Carteles educativos"
   ahora lista los 11 carteles con nombre, categoría, unidad y orden
   correctos, y que la tabla "Configuración de carteles" los sigue mostrando
   con el nombre correcto.

5. Doble chequeo opcional por API directa:

   ```bash
   curl http://127.0.0.1:8000/api/v1/carteles | python3 -m json.tool
   ```

   Debe devolver `"count": 11` (o más, si ya existían carteles adicionales
   creados a mano).

## Si algo falla

No reintentar `--apply` a ciegas. Revisar el mensaje de error concreto
(problema de conexión a Mongo, clave duplicada, validación de Pydantic,
etc.) antes de volver a correr el script — el script es idempotente, así que
un segundo intento después de corregir el problema es seguro y no duplicará
los carteles ya creados.
