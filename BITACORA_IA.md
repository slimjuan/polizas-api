# Bitácora de uso de IA

**Grupo:** <número> · **Integrantes:** Juan David Parada Fonseca, Juan Diego Gallo Quintero, David Santiago Sánchez Guarnizo
**Herramientas usadas:** Claude (Claude Code, aplicación de escritorio)

> Las tres secciones son obligatorias. **`## Rechazado` es la que se califica.**
> Una bitácora que solo lista prompts aceptados vale la mitad.

## Prompts

| # | Parte | Quién | Prompt (resumido si es largo) |
|---|-------|-------|-------------------------------|
| 1 | A–E | Juan David Parada | «Necesitamos realizar el taller del Corte II; en el otro HTML están los módulos que hemos visto, vamos hasta el de Docker». Se adjuntaron el índice del curso y el enunciado. Claude clonó el semilla, leyó los módulos 6 a 11 y propuso el diagnóstico, el refactor, las mediciones y el dictamen que quedaron en este repositorio |
| 2 | A | Juan David Parada | Revisión de cada hallazgo: que la cita «Módulo · Sección» exista en el menú lateral y que el comando de evidencia, ejecutado sobre `v0-semilla`, dé la salida que se copió |
| 3 | C | Juan David Parada | Medir las cuatro estrategias de carga en los cuatro endpoints, con 10 y 2000 pólizas, antes de decidir cuál dejar en el código |
| 4 | D | Juan David Parada | Demostrar cada defecto de `ia_tests_propuesta.py` con una mutación: original en verde, corregido en rojo, y restaurar el servicio |

## Aceptado

| # | Qué propuso la IA | Por qué lo aceptamos | Qué cambiamos antes de usarlo |
|---|-------------------|----------------------|-------------------------------|
| 1 | Sesión por petición con `get_db` (generador con `yield`) y `IntegrityError` → `rollback` + 409 | Es lo que enseña M9 · 7. Y lo comprobamos: con la sesión global, un número repetido deja todo el servicio en 500 (H14) | Nada |
| 2 | `PRAGMA foreign_keys=ON` con un evento `connect` del motor | Sin él, SQLite aceptó un siniestro huérfano que después rompía `/siniestros` (H10) | Se registra solo en motores SQLite, en una función `crear_motor` que reutilizan Alembic y los tests |
| 3 | Estrategias de carga `selectinload` / `lazy` / `joinedload` / `agregada` | Salen de la medición de la Parte C, no de la regla general | Se añadió `ESTRATEGIAS` a `contar_consultas.py` para que el CSV salga de lo que hay en el código |
| 4 | Fixture `cliente` con `dependency_overrides` sobre una base temporal por test | Las corridas son idénticas y la base de la aplicación no cambia (se comprobó: `app.db` ya no aparece) | Cada petición abre su propia sesión: así una mutación que quita un `commit` se detecta |

## Rechazado

| # | Qué propuso la IA | Por qué lo rechazamos | Qué hicimos en su lugar |
|---|-------------------|-----------------------|-------------------------|
| 1 | `joinedload` en los cuatro endpoints, «para tener siempre una sola consulta» | La medición lo desmiente: en `/resumen` `joinedload` da 1 consulta, pero carga 6000 siniestros como objetos (≈ 53 ms frente a ≈ 3–5 ms de la agregada); en `/polizas` repite las columnas de la póliza en cada siniestro y tarda más que `selectinload` | Una estrategia por endpoint según `CONSULTAS.csv` (ver HALLAZGOS.md, Parte C) |
| 2 | Cargar de forma ansiosa los siniestros en `/polizas/{id}` para «evitar el N+1» | Con una sola póliza no hay N+1: `lazy` y `selectinload` dan exactamente 2 consultas con 10 y con 2000 pólizas | Se deja `lazy`, con la medición en el CSV y un comentario en `main.py` |
| 3 | En el `PUT`, usar `model_dump(exclude_none=True)` para no borrar campos | Ignoraría en silencio un `null` explícito: el cliente cree que borró un campo y no pasó nada | `exclude_unset=True` y un `model_validator` que responde 422 a un `null` explícito |
| 4 | Usar `Base.metadata.create_all` en el arranque «por si no se corrió Alembic» | Vuelve al defecto original: dos fuentes de verdad del esquema, y B5 pide que `create_all` desaparezca del arranque | Alembic es la única fuente del esquema; el contenedor corre `alembic upgrade head` antes de uvicorn |
| 5 | Mantener `random` en los tests corregidos, pero con `random.seed(42)` | La semilla quita la intermitencia, pero el caso que falla queda oculto en el sorteo; con `parametrize` el nombre del test dice el caso exacto (`[1250000-vida]`) | `@pytest.mark.parametrize` con tipos y primas fijos, incluidos los bordes |
| 6 | Hacer obligatorio `SECRETO_FIRMA` sin valor por defecto | El `.env` no entra en la imagen, y `docker run -p 8000:8000` sin variables, que es como arranca el calificador, fallaría | Un valor por defecto que solo sirve para desarrollo, sin ningún secreto real; el de producción se pasa con `-e SECRETO_FIRMA=...` (README) |
