# Dictamen sobre `ia_tests_propuesta.py` — Parte D

**Grupo:** <número> · **Integrantes:** Juan David Parada Fonseca

> Las tres mutaciones se aplicaron sobre el servicio ya corregido (Parte B), se
> corrieron el test original y el corregido, y se restauró el archivo con
> `git checkout -- <archivo>` (`git status` limpio después de cada una). La
> batería corregida está en `tests/test_ia_corregido.py` y pasa entera sobre el
> código sano (`pytest tests/test_ia_corregido.py` → 37 passed).

## Defecto 1

- **Qué está mal:** tests que no pueden fallar. Sus aserciones aceptan todos los resultados posibles: `test_consultar_poliza_inexistente` admite `status_code in (200, 404)`, `test_listar_polizas_no_falla` admite cualquier código `< 500`, `test_crear_poliza_responde` admite `(200, 201, 422)` —éxito y rechazo a la vez— y `test_score_de_poliza_recien_creada` acepta `"puntaje" in r.json() or "error" in r.json()`. Un test que pasa con el servicio bien y con el servicio mal no aporta información: su verde no significa nada.
- **Por qué es un defecto** (M10 · 4. Framework pytest): un test es una afirmación falsable sobre un resultado esperado; si la aserción es verdadera para todas las salidas posibles, no hay ningún defecto que pueda detectar. Además el contrato (M6 · 5. Routing y CRUD) fija un único código por situación: 404 para un recurso inexistente, 201 al crear.
- **Cómo lo comprobamos:** mutación que deja de devolver el 404 en `GET /polizas/{id}` y vuelve al comportamiento del semilla (200 con `{"error": ...}`). El test original sigue en verde; el corregido se pone en rojo.

```diff
--- a/main.py
+++ b/main.py
@@ -5,6 +5,7 @@
 from fastapi import Depends, FastAPI, HTTPException, status
+from fastapi.responses import JSONResponse
 from sqlalchemy import select, text
@@ -63,7 +64,10 @@
 @app.get("/polizas/{id_poliza}", response_model=PolizaSalida)
 def obtener_poliza(id_poliza: int, db: Session = Depends(get_db)):
-    return _poliza_o_404(db, id_poliza)
+    poliza = db.get(Poliza, id_poliza)
+    if poliza is None:
+        return JSONResponse({"error": f"no existe la póliza {id_poliza}"})
+    return poliza
```

```
$ pytest ia_tests_propuesta.py -q -k inexistente
.                                                                        [100%]
1 passed, 5 deselected in 0.65s
```

```
$ pytest tests/test_ia_corregido.py -q -k recurso_inexistente
FAILED tests/test_ia_corregido.py::test_recurso_inexistente_da_404[get-/polizas/999999-None]
1 failed, 3 passed, 33 deselected in 1.30s
```

- **Corrección:** cada test afirma un único resultado exacto. `test_recurso_inexistente_da_404` exige 404 en las cuatro rutas que reciben un identificador (`GET` y `PUT /polizas/{id}`, `POST /polizas/{id}/siniestros`, `POST /score`); la creación exige 201; la validación exige 422 (`test_entrada_invalida_da_422_y_no_se_guarda`).

## Defecto 2

- **Qué está mal:** tests que no prueban lo que dicen probar. (a) El «aislamiento» es falso: el archivo define su propia función `get_db` y registra `app.dependency_overrides[get_db] = get_db`, pero esa clave no es la dependencia que usa la aplicación (`database.get_db`), así que la sustitución nunca se aplica y todas las pruebas escriben en la base real. Lo medimos: con `app.db` vacía, cada corrida de `pytest ia_tests_propuesta.py` deja 7 pólizas más (0 → 7 → 14). Aunque la clave fuera la correcta, un `MagicMock` no es una base de datos: ninguna consulta tendría resultado real. (b) Los tests de creación dicen probar que se crea una póliza, pero solo miran el código de la respuesta: nunca vuelven a leer lo creado, y el de puntuación acepta un error como respuesta válida.
- **Por qué es un defecto** (M10 · 5. TestClient de FastAPI): la sustitución con `app.dependency_overrides` se hace sobre la función de dependencia que la aplicación declara en `Depends`, no sobre una homónima; y M9 · 7. SQLite local e integración con FastAPI: lo que no se confirma con `commit` se descarta al cerrar la sesión de la petición, así que «crear» solo está probado si una petición posterior lo lee.
- **Cómo lo comprobamos:** mutación que cambia el `commit` de `POST /polizas` por un `flush`: la póliza recibe `id` y la respuesta sale 201, pero al cerrarse la sesión la escritura se descarta. Los dos tests de creación originales siguen en verde; el corregido, que vuelve a leer lo creado, se pone en rojo en sus 12 casos.

```diff
--- a/main.py
+++ b/main.py
@@ -44,7 +44,7 @@ def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
     poliza.siniestros = [Siniestro(**s.model_dump()) for s in datos.siniestros]
     db.add(poliza)
     try:
-        db.commit()
+        db.flush()
     except IntegrityError:
         db.rollback()
```

```
$ pytest ia_tests_propuesta.py -q -k "crear_poliza_responde or primas_variadas"
..                                                                       [100%]
2 passed, 4 deselected in 0.66s
```

```
$ pytest tests/test_ia_corregido.py -q -k devuelve_201_y_persiste
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[4999999.99-hogar]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[4999999.99-vida]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[50000000-auto]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[50000000-hogar]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[50000000-vida]
12 failed, 25 deselected in 0.14s
```

- **Corrección:** la fixture `cliente` de `tests/conftest.py` sustituye `database.get_db` —la dependencia real— por sesiones sobre una base SQLite temporal, nueva en cada test, y cada petición abre su propia sesión, como en producción. Los tests comprueban el efecto: `test_crear_poliza_devuelve_201_y_persiste` vuelve a pedir la póliza por `GET` y exige que sea igual; `test_put_parcial_cambia_solo_lo_enviado_y_persiste`, `test_declarar_siniestro_da_201_y_persiste` y `test_score_de_poliza_recien_creada_queda_registrado` leen después de escribir. Con eso un `commit` ausente en cualquiera de las cuatro rutas que escriben se detecta.

## Defecto 3

- **Qué está mal:** tests que unas veces pasan y otras no. `_poliza()` sortea el `tipo` con `random.choice` y la `prima` con `random.uniform`, sin semilla: cada corrida prueba datos distintos, así que el resultado depende del sorteo y no del código. Hoy no se nota porque las aserciones aceptan cualquier cosa (Defecto 1), pero en cuanto se endurecen el test se vuelve intermitente: un fallo que solo afecta a un tipo o a un rango de primas aparece en unas corridas y desaparece en otras, y un fallo que no se puede reproducir no se puede depurar.
- **Por qué es un defecto** (M10 · 4. Framework pytest): las pruebas deben ser deterministas —el material fija la semilla (`random.seed`) precisamente por eso— y la variedad de casos se consigue con `@pytest.mark.parametrize` y datos fijos, no con azar; ver también M10 · 7. Reproducibilidad sin Docker: el mismo commit debe dar siempre el mismo resultado.
- **Cómo lo comprobamos:** mutación en el validador para que rechace pólizas de tipo `vida`. El test original sigue en verde. Además corrimos 8 veces, sobre el MISMO código mutado, una versión del original con la aserción endurecida (`== 201`) pero con los datos aleatorios: unas corridas pasan y otras fallan. El corregido falla siempre, y en los casos exactos.

```diff
--- a/esquemas.py
+++ b/esquemas.py
@@ -8,7 +8,7 @@ from typing import Literal, Optional
 
 from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
 
-TipoPoliza = Literal["auto", "hogar", "vida"]
+TipoPoliza = Literal["auto", "hogar"]
```

```
$ pytest ia_tests_propuesta.py -q -k "crear_poliza_responde or primas_variadas"
..                                                                       [100%]
2 passed, 4 deselected in 0.66s

# misma prueba con `== 201` pero datos aleatorios, 8 corridas sobre el mismo código:
2 passed, 4 deselected in 0.66s
2 failed, 4 deselected in 0.68s
2 failed, 4 deselected in 0.67s
1 failed, 1 passed, 4 deselected in 0.68s
2 failed, 4 deselected in 0.68s
1 failed, 1 passed, 4 deselected in 0.68s
1 failed, 1 passed, 4 deselected in 0.69s
1 failed, 1 passed, 4 deselected in 0.68s
```

```
$ pytest tests/test_ia_corregido.py -q -k devuelve_201_y_persiste
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[0.01-vida]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[1250000-vida]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[4999999.99-vida]
FAILED tests/test_ia_corregido.py::test_crear_poliza_devuelve_201_y_persiste[50000000-vida]
4 failed, 8 passed, 25 deselected in 0.12s
```

- **Corrección:** sin `random`. La variedad se declara con `@pytest.mark.parametrize`: los tres tipos × cuatro primas que incluyen los bordes (0.01, un valor típico, 4 999 999.99 y 50 000 000), y casos inválidos fijos para el 422. Los números de póliza salen de un contador en la fixture `poliza_valida`, no de `uuid`, así que cada corrida es idéntica a la anterior y un fallo señala el caso exacto (`[1250000-vida]`).
