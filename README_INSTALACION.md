# Huerto2027 — Instalación

Stack: backend FastAPI+MongoDB (puerto 8000), frontend legacy estático (puerto 5500), frontend2 estático (puerto 5600).

## 1. Descomprimir
```bash
unzip huerto2027.zip -d /opt/huerto2027
cd /opt/huerto2027
```

## 2. Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```


Arrancar:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Producción: correr bajo systemd/supervisor, no en foreground.

## 3. Seed inicial (una sola vez, OBLIGATORIO)
Sin este paso los gráficos funcionan pero **los carteles no aparecen** (la colección de MongoDB queda vacía).
```bash
python backend/scripts/migrate_educational_posters.py
python backend/scripts/seed_campaign_lettuce_ranges.py
```
Verificar que cargó:
```bash
curl http://localhost:8000/api/v1/carteles   # debe devolver "count" > 0
```

## 4. Frontend
Estático, sin build. Servir `frontend2/` (versión activa) y opcionalmente `frontend/` (legacy).

```bash
cd frontend2 && python3 -m http.server 5600
cd frontend  && python3 -m http.server 5500   # opcional, legacy
```

En producción, usar Nginx en vez de `http.server`:
```nginx
location /api/ { proxy_pass http://127.0.0.1:8000/api/; }
location /     { root /opt/huerto2027/frontend2; try_files $uri $uri/ /index.html; }
```

**Antes de exponer al público**, editar `API_BASE_URL` en `frontend2/configuracion.js` (y `frontend/js/configuracion.js` si se usa) para que apunte al dominio/IP real del backend, no a `127.0.0.1:8000`.

## 5. Verificación
```bash
curl http://localhost:8000/api/v1/           # backend responde
curl -I http://localhost:5600/                # frontend2 sirve
```
Abrir el frontend en navegador y confirmar que carga datos sin errores CORS/502 en consola.
