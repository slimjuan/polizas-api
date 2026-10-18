# polizas-api

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas
y los siniestros que se les declaran, resume la cartera y puntúa el riesgo de
cada póliza con un modelo, guardando cada predicción.

Stack: FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · pytest · Docker.
Python **3.11**.

## Arranque local

```bash
python3.11 -m venv .venv
source .venv/bin/activate            # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # y cambien los secretos de ejemplo
alembic upgrade head                 # crea el esquema en la base de DATABASE_URL
uvicorn main:app --host 127.0.0.1 --port 8000
```

- La configuración se lee de `.env` o de variables de entorno (`config.py`). La
  base es la que diga `DATABASE_URL` (por defecto `sqlite:///app.db`).
- El esquema **no** se crea al arrancar: lo crea `alembic upgrade head`. Corran
  ese comando cada vez que cambie la base o haya migraciones nuevas.
- `--reload` solo es para desarrollo; no se usa en producción ni en el contenedor.
- Datos de ejemplo, con el servicio corriendo: `python sembrar_datos.py --polizas 12`.

## En contenedor

```bash
docker build -t polizas-api .
docker run -d --name polizas -p 8000:8000 -v polizas-datos:/app/data polizas-api
docker ps --filter name=polizas
curl http://localhost:8000/health
docker logs polizas
```

`docker ps` debe mostrar el estado `healthy`; `/health` responde
`{"estado":"ok","base_de_datos":true}`. El contenedor aplica las migraciones al
arrancar y escucha en `0.0.0.0:8000`. En Windows PowerShell, usen `curl.exe` en lugar de
`curl` si este nombre está asociado a `Invoke-WebRequest`.

Para probar persistencia, creen una póliza desde `http://localhost:8000/docs` y
consúltenla con `curl http://localhost:8000/polizas`. Reiniciar el mismo contenedor
conserva su capa escribible:

```bash
docker restart polizas
curl http://localhost:8000/polizas
```

El volumen permite conservar los datos incluso al reemplazar el contenedor. El comando
inicial ya monta `polizas-datos` en `/app/data`; para probarlo, eliminen el contenedor y
creen otro con el mismo volumen:

```bash
docker rm -f polizas
docker run -d --name polizas -p 8000:8000 -v polizas-datos:/app/data polizas-api
curl http://localhost:8000/polizas
```

La póliza creada debe seguir apareciendo. Para cerrar la demo, eliminen el contenedor;
si también quieren borrar los datos persistidos, eliminen el volumen explícitamente:

```bash
docker rm -f polizas
docker volume rm polizas-datos
```

El contenedor corre como usuario no root y tiene `HEALTHCHECK` contra `/health`. La
imagen no lleva `.env` ni base de datos (ver `.dockerignore`). Los secretos se pasan al
ejecutar, por ejemplo: `docker run -e SECRETO_FIRMA=... -p 8000:8000 polizas-api`.

**Persistencia:** la base vive en `/app/data/app.db`, dentro del contenedor.
Un volumen nombrado como `polizas-datos` la conserva entre contenedores distintos.

## Endpoints

| Método | Ruta | Respuesta |
|---|---|---|
| POST | `/polizas` | 201 con la póliza creada · 409 si el número ya existe · 422 |
| GET | `/polizas` | 200, cada póliza con sus siniestros |
| GET | `/polizas/{id}` | 200 · 404 |
| PUT | `/polizas/{id}` | 200, actualización **parcial** · 404 · 422 |
| POST | `/polizas/{id}/siniestros` | 201 · 404 si la póliza no existe · 422 |
| GET | `/siniestros` | 200, cada siniestro con el número de su póliza |
| GET | `/resumen` | 200, número de siniestros y monto total por póliza |
| POST | `/score` | 200 con `numero`, `puntaje` y `alto_riesgo`; registra la predicción · 404 · 422 |
| GET | `/predicciones` | 200, histórico con el `numero` de la póliza |
| GET | `/health` | 200, indica si la base de datos responde |

Documentación interactiva: `http://localhost:8000/docs`.

### Ejemplo

```bash
curl -X POST localhost:8000/polizas \
  -H "Content-Type: application/json" \
  -d '{"numero": "POL-2026-09001", "asegurado": "Ana Rueda", "tipo": "auto", "prima": 1250000,
       "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14"}'
curl -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero": "POL-2026-09001"}'
```

## Pruebas

```bash
pytest
```

Corre `tests/`: la batería de contrato (`test_contrato.py`), los tests propios y la
batería corregida de la Parte D. Los tests sustituyen la sesión con
`app.dependency_overrides` sobre bases temporales: no tocan la base de la aplicación y
dan el mismo resultado en corridas sucesivas.

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `main.py` | Rutas HTTP: valida la entrada, llama al dominio y traduce errores a 404/409/422 |
| `esquemas.py` | Esquemas Pydantic de entrada (validación) y de salida (contrato) |
| `modelos.py` | Tablas SQLAlchemy 2.0 |
| `servicios.py` | Firma, puntuación de riesgo y resumen de cartera |
| `database.py` | Motor, claves foráneas en SQLite y `get_db` (sesión por petición) |
| `config.py` | `Settings` con `BaseSettings` y `get_settings()` con `lru_cache` |
| `alembic/` | Migraciones del esquema |

## Entregables del taller

`EQUIPO.md`, `HALLAZGOS.md` (partes A y C), `CONSULTAS.csv`, `DICTAMEN_IA.md`,
`tests/test_ia_corregido.py` y `BITACORA_IA.md`. Comprobación de forma:
`python verificar_entrega.py`.
