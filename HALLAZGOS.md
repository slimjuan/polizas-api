# Hallazgos — Parte A

**Grupo:** <número> · **Integrantes:** Juan David Parada Fonseca, Juan Diego Gallo Quintero, David Santiago Sánchez Guarnizo

> Todos los comandos se ejecutaron **en este orden**, sobre un checkout limpio de
> `v0-semilla` (con su `app.db` original) y con el servicio levantado como dice su
> README (`uvicorn main:app --host 127.0.0.1 --port 8000`), desde la raíz del
> repositorio. Dos avisos para reproducirlos: H9 y H10 modifican datos (la póliza 12
> y un siniestro huérfano), y **H14 va de último a propósito**: deja la sesión
> compartida inservible y, desde ahí, todo el servicio responde 500 hasta reiniciarlo.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | Las claves `SECRETO_FIRMA` y `CLAVE_API_REASEGURO` están escritas en `config.py` y quedan en la historia de git | Secretos en el código («para que el equipo pueda probar sin configurar nada»); cualquiera con acceso al repositorio los tiene | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `git grep -n "CLAVE_API_REASEGURO = " v0-semilla -- config.py` | `v0-semilla:config.py:5:CLAVE_API_REASEGURO = "rk-polizas-2026-4b9f0a3d"` | Se leen con `BaseSettings` desde `.env` (no versionado); `.env.example` solo trae valores de ejemplo. Las claves filtradas deben rotarse: siguen en la historia |
| H2 | Con `DATABASE_URL` apuntando a otra base, el servicio sigue usando `app.db` | `DATABASE_URL` está escrita a mano en `config.py`; nada lee el entorno | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `DATABASE_URL=sqlite:///otra.db python -c "import database; print(database.engine.url)"` | `sqlite:///app.db` | `Settings.database_url` se lee de `DATABASE_URL`; `get_settings()` con `lru_cache`, inyectada con `Depends`; Alembic usa la misma URL |
| H3 | `POST /polizas` responde 200 al crear | La ruta no declara `status_code=201` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8000/polizas -H 'Content-Type: application/json' -d '{"numero":"POL-H3-'$(python -c 'import uuid;print(uuid.uuid4().hex[:8])')'","asegurado":"Ana Rueda","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31"}'` | `200` | `status_code=201` en `POST /polizas` y `POST /polizas/{id}/siniestros` |
| H4 | Las respuestas exponen `token_firma`, un dato interno derivado del secreto | Las rutas devuelven el objeto ORM o diccionarios armados a mano, sin `response_model` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/1 \| grep -o '"token_firma"'` | `"token_firma"` | `response_model` en todas las rutas con esquemas de salida (`PolizaSalida`, etc.) que no declaran `token_firma` |
| H5 | Una póliza inexistente devuelve 200 con `{"error": ...}` en `GET` y `PUT /polizas/{id}` y en `POST /score` | Se devuelve un diccionario de error en vez de lanzar `HTTPException(404)` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -w ' %{http_code}' localhost:8000/polizas/999999` | `{"error":"no existe la póliza 999999"} 200` | `_poliza_o_404` lanza `HTTPException(404)`; `/score` también da 404 |
| H6 | El asegurado se guarda como `null` aunque se envíe un nombre válido | `normalizar_asegurado` calcula el nombre limpio pero no lo devuelve: el validador retorna `None` | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H 'Content-Type: application/json' -d '{"numero":"POL-H6-'$(python -c 'import uuid;print(uuid.uuid4().hex[:8])')'","asegurado":"Carla Ibáñez","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31"}' \| grep -o '"asegurado":[^,]*'` | `"asegurado":null` | El validador devuelve el valor normalizado; la columna `asegurado` pasa a NOT NULL |
| H7 | Se acepta una póliza con `fecha_fin` anterior a `fecha_inicio` | No hay validación cruzada entre campos | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8000/polizas -H 'Content-Type: application/json' -d '{"numero":"POL-H7-'$(python -c 'import uuid;print(uuid.uuid4().hex[:8])')'","asegurado":"Ana Rueda","tipo":"auto","prima":1000,"fecha_inicio":"2027-01-14","fecha_fin":"2026-01-15"}'` | `200` | `model_validator(mode="after")` exige `fecha_fin > fecha_inicio`; el `PUT` hace la misma comprobación |
| H8 | Se acepta un siniestro anidado con monto negativo y descripción de un carácter | `siniestros` está tipado como `list[dict]`: el contenido no se valida y se copia con `.get()` y valores por defecto | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:8000/polizas -H 'Content-Type: application/json' -d '{"numero":"POL-H8-'$(python -c 'import uuid;print(uuid.uuid4().hex[:8])')'","asegurado":"Ana Rueda","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[{"fecha":"2026-03-02","monto":-50,"descripcion":"x"}]}'` | `200` | `siniestros: list[SiniestroEntrada]`, submodelo con `monto` > 0 y `descripcion` de 3 a 200 caracteres |
| H9 | Un `PUT` que solo cambia la prima borra `asegurado`, `tipo` y `fecha_fin` | `model_dump()` sin `exclude_unset` incluye en `None` los campos no enviados y se escriben todos | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -X PUT localhost:8000/polizas/12 -H 'Content-Type: application/json' -d '{"prima":999000}' \| grep -o '"tipo":[^,]*'` | `"tipo":null` | `model_dump(exclude_unset=True)`; un `null` explícito se rechaza con 422 |
| H10 | Se registra un siniestro para una póliza que no existe (200) y desde entonces `GET /siniestros` responde 500 | No se comprueba que la póliza exista y SQLite trae `PRAGMA foreign_keys` apagado: la fila huérfana entra y luego `s.poliza` es `None` | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w '%{http_code} ' -X POST localhost:8000/polizas/999999/siniestros -H 'Content-Type: application/json' -d '{"fecha":"2026-03-02","monto":850000,"descripcion":"Choque leve"}'; curl -s -o /dev/null -w '%{http_code}' localhost:8000/siniestros` | `200 500` | 404 si la póliza no existe y `PRAGMA foreign_keys=ON` en cada conexión (evento `connect` del motor) |
| H11 | Correr `tests/test_api.py` escribe una póliza de prueba en la base de la aplicación (y la segunda corrida falla por número repetido) | Los tests usan la aplicación tal cual, sin sustituir la sesión: no hay aislamiento | M10 · 6. Fixtures en pytest | `v0-semilla` | `python -m pytest -q -p no:cacheprovider tests/test_api.py >/dev/null 2>&1; python -c "import sqlite3; print(sqlite3.connect('app.db').execute(\"select numero from polizas where numero like 'POL-TEST%'\").fetchall())"` | `[('POL-TEST-00001',)]` | Fixture `cliente` en `tests/conftest.py` con `app.dependency_overrides[get_db]` sobre una base temporal por test |
| H12 | El `Dockerfile` usa `python:latest` y arranca uvicorn en `127.0.0.1` con `--reload`: desde el host, `docker run -p 8000:8000` no responde | Base sin fijar; dentro del contenedor 127.0.0.1 solo escucha la interfaz local; además corre como root, sin multietapa ni `HEALTHCHECK` | M11 · 6. Estructura de un Dockerfile | `v0-semilla` | `grep -c -e 'python:latest' -e '"127.0.0.1"' Dockerfile` | `2` | Multietapa sobre `python:3.11.9-slim-bookworm`, usuario no root, `HEALTHCHECK` contra `/health`, `CMD` con `--host 0.0.0.0` y sin `--reload` |
| H13 | El entorno no es reproducible: `app.db` está versionada y `requirements.txt` no fija versiones | `.gitignore` solo cubre `*.pyc`; las dependencias se instalan en la versión del día | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `echo $(git ls-files '*.db') $(grep -vc '==' requirements.txt)` | `app.db 8` | `requirements.txt` con `==` en todas las líneas (`pip freeze`); `.gitignore` cubre `.env`, `*.db` y el entorno virtual; `app.db` sale del índice y el esquema lo crea Alembic |
| H14 | Un número de póliza repetido devuelve 500 en vez de 409, y desde ese momento todo el servicio responde 500 | Una única sesión a nivel de módulo compartida por todas las peticiones: el `IntegrityError` no se captura, la sesión queda en estado fallido sin `rollback` y arrastra a las peticiones siguientes | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w '%{http_code} ' -X POST localhost:8000/polizas -H 'Content-Type: application/json' -d '{"numero":"POL-2026-00001","asegurado":"Ana Rueda","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31"}'; curl -s -o /dev/null -w '%{http_code}' localhost:8000/polizas` | `500 500` | Sesión por petición con `get_db` (generador con `yield` que cierra); `IntegrityError` → `rollback` y 409 |

**Otros defectos observados que no van en la tabla** porque los cubre una fila de arriba
o son consecuencia directa de ella: `create_all` en el arranque en vez de migraciones
(B5), `/predicciones` sin el `numero` de la póliza (se resolvió con un `JOIN` y su
esquema de salida), la ausencia de `/health` (B10) y el README, que recomendaba
`--reload` en producción y presentaba los secretos en `config.py` como una comodidad.

**Modificaciones a `contar_consultas.py`:** se añadió el diccionario `ESTRATEGIAS`,
que rellena la columna `estrategia` con la estrategia que quedó en `main.py` para cada
endpoint. Al reproducirlo en Windows también se normalizó la ruta SQLite y se ubicó la
base temporal dentro del proyecto; al finalizar se cierra el motor antes de limpiar el
archivo temporal. La siembra y la lógica del conteo no se cambiaron.

---

# Parte C — Interpretación de las consultas

Reproduje `python contar_consultas.py` en Windows con Python 3.12.10 (entorno virtual
creado con `requirements.txt`). El script aplicó la migración a una base SQLite temporal,
sembró 10 y 2000 pólizas con tres siniestros por póliza y midió cada endpoint con
TestClient; los resultados quedaron en `CONSULTAS.csv`. En ambos tamaños los conteos
coinciden con la medición previa: `/polizas` hizo 2 y 5 consultas, `/polizas/{id}` hizo
2 y 2, `/siniestros` hizo 1 y 1, y `/resumen` hizo 1 y 1. Los tiempos medidos en esta
máquina fueron, respectivamente, 3.9/162.9 ms, 2.4/2.4 ms, 2.2/126.5 ms y 3.7/13.6 ms;
varían según equipo y carga. Antes de decidir medimos las cuatro estrategias en cada
endpoint con la misma siembra y la misma serialización que usa la ruta:

| Endpoint | lazy (10 → 2000) | selectinload | joinedload | agregada | Quedó en el código |
|---|---|---|---|---|---|
| `/polizas` | 11 → 2001 | 2 → 5 | 1 → 1 | no aplica | `selectinload` |
| `/polizas/{id}` | 2 → 2 | 2 → 2 | 1 → 1 | no aplica | `lazy` |
| `/siniestros` | 11 → 2001 | 2 → 5 | 1 → 1 | no aplica | `joinedload` |
| `/resumen` | 11 → 2001 | 2 → 5 | 1 → 1 (≈ 53 ms) | 1 → 1 (≈ 3–5 ms) | `agregada` |

## `/polizas`

**Estrategia: `selectinload`. Consultas: 2 con 10 pólizas, 5 con 2000.** La primera
consulta trae las pólizas; después SQLAlchemy pide los siniestros de todas con
`WHERE poliza_id IN (...)`. Con 10 pólizas es un solo `IN`, y el total es 2. Con 2000 sube a
5, y eso nos sorprendió: no es constante porque `selectinload` parte la lista de
identificadores en lotes de 500 (1 + ⌈2000 / 500⌉ = 1 + 4). Crece una consulta por cada
500 pólizas, no una por póliza como `lazy` (2001). Descartamos `joinedload` aunque da 1
consulta: en una colección uno-a-muchos, el `JOIN` repite todas las columnas de la póliza
en cada uno de sus siniestros (6000 filas para 2000 pólizas), y el ORM tiene que
deduplicarlas. En nuestra medición tardó más que `selectinload` (≈ 64 ms frente a ≈ 58 ms):
una consulta menos no significa menos trabajo. Aquí la regla «cargar todo de una vez»
empeora el resultado.

## `/polizas/{id}`

**Estrategia: `lazy`. Consultas: 2 con 10 pólizas y 2 con 2000.** `db.get` trae la
póliza y, al serializar `siniestros`, la carga perezosa emite una segunda consulta solo
para los siniestros de esa póliza. El número no depende del tamaño de la cartera porque
siempre se trata de una sola póliza: el N+1 aparece cuando se recorre una lista, y aquí
N = 1. Medimos la alternativa «de una vez»: `selectinload` da exactamente las mismas 2
consultas, y `joinedload`, 1, con una diferencia de décimas de milisegundo. Dejamos `lazy`
a sabiendas de que incumple la regla, porque la medición dice que da igual. Este es el
caso en que hay que contar antes de decidir.

## `/siniestros`

**Estrategia: `joinedload`. Consultas: 1 con 10 pólizas y 1 con 2000.** Cada siniestro
necesita el número de su póliza, y la relación es muchos-a-uno: un `LEFT OUTER JOIN` trae
cada siniestro con su única póliza en la misma fila, sin multiplicar filas (30 filas con
10 pólizas, 6000 con 2000). Por eso el conteo es 1 en los dos tamaños. Con `lazy` serían
1 + 2000 consultas, una por póliza distinta: el mapa de identidades evita repetir la misma
póliza, pero no evita pedir cada una. `selectinload` también sería defendible (2 → 5), pero
aquí el `JOIN` no duplica nada y gana en consultas y en tiempo.

## `/resumen`

**Estrategia: `agregada`. Consultas: 1 con 10 pólizas y 1 con 2000.** El endpoint solo
necesita, por póliza, cuántos siniestros tiene y cuánto suman. Una sola consulta con
`LEFT OUTER JOIN`, `COUNT` y `SUM` y `GROUP BY poliza.id` hace ese trabajo en la base y
devuelve una fila por póliza. No viaja ningún siniestro a Python, y el `LEFT JOIN` conserva
las pólizas sin siniestros (0 y 0.0). `joinedload` también da 1 consulta, pero carga los
6000 siniestros como objetos para contarlos en Python: en la medición tardó ≈ 53 ms contra
≈ 3–5 ms de la agregada. Con el mismo número de consultas, el trabajo es mucho mayor. El
semilla lo hacía con carga perezosa: 1 + N consultas (11 y 2001).
