"""
Instrumento de la Parte C: cuenta las sentencias SQL que emite cada endpoint.

    python contar_consultas.py                      # 10 y 2000 pólizas, escribe CONSULTAS.csv
    python contar_consultas.py --tamanos 10 200     # para probar rápido

Qué hace:
  1. Apunta la aplicación a una base de datos TEMPORAL poniendo DATABASE_URL
     antes de importarla, y aplica las migraciones si hay alembic.ini.
     Si la aplicación no honra DATABASE_URL, se avisa: entonces está
     sembrando en la base de datos de la aplicación, y eso es un hallazgo.
  2. Engancha un contador a `before_cursor_execute` del motor de SQLAlchemy —a
     nivel de clase, así que cuenta cualquier engine que exista— y levanta la
     aplicación en proceso con TestClient.
  3. Siembra por la API (sembrar_datos.sembrar) hasta cada tamaño, pide cada
     endpoint una vez para calentar y otra para contar, y escribe el CSV.

Lo que NO hace, y es lo que se califica: decidir la `estrategia` de carga de
cada endpoint, dejarla en el código y explicar los números. La columna
`estrategia` la rellenan ustedes; si la dejan vacía, el archivo no vale.

Se califica `consultas_sql`, que es determinista; `tiempo_ms` cambia de una
máquina a otra y solo sirve para interpretar.

Pueden modificarlo. Si lo hacen, dígan­lo en HALLAZGOS.md.
"""
import argparse
import csv
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ENDPOINTS = ["/polizas", "/polizas/{id}", "/siniestros", "/resumen"]
# Modificación del grupo: la estrategia que quedó en main.py para cada endpoint.
# Si se cambia una en el código, se cambia aquí; HALLAZGOS.md explica cada una.
ESTRATEGIAS = {"/polizas": "selectinload", "/polizas/{id}": "lazy",
               "/siniestros": "joinedload", "/resumen": "agregada"}
COLUMNAS = ["endpoint", "estrategia", "n_polizas", "consultas_sql", "tiempo_ms"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tamanos", nargs="+", type=int, default=[10, 2000])
    ap.add_argument("--por-poliza", type=int, default=3)
    ap.add_argument("--salida", default="CONSULTAS.csv")
    a = ap.parse_args()

    raiz = Path(__file__).parent.resolve()
    os.chdir(raiz)
    sys.path.insert(0, str(raiz))

    # 1 · base de datos temporal, ANTES de importar la aplicación
    # En Windows el directorio temporal del sistema puede no estar disponible
    # para el proceso; mantener la base de prueba dentro del proyecto también
    # garantiza que el directorio temporal es escribible.
    temporal = tempfile.TemporaryDirectory(prefix="consultas-", dir=raiz)
    carpeta = Path(temporal.name)
    db = carpeta / "consultas.db"
    # SQLite URLs usan barras incluso en Windows; las barras invertidas de
    # Path.as_posix() evitan que SQLite interprete mal la ruta absoluta.
    os.environ["DATABASE_URL"] = f"sqlite:///{db.as_posix()}"
    if (raiz / "alembic.ini").exists():
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    # 2 · el contador, a nivel de clase
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    contador = {"n": 0}

    @event.listens_for(Engine, "before_cursor_execute")
    def _contar(conn, cursor, statement, parameters, context, executemany):
        contador["n"] += 1

    from fastapi.testclient import TestClient
    from main import app
    from sembrar_datos import sembrar

    filas = []
    with TestClient(app, raise_server_exceptions=False) as cliente:
        sembradas, primer_id = 0, None
        for n in a.tamanos:
            ids = sembrar(cliente, n - sembradas, a.por_poliza, prefijo="POL-C", desde=sembradas + 1)
            primer_id = primer_id or ids[0]
            sembradas = n
            if not (db.exists() and db.stat().st_size > 0):
                print("AVISO: la aplicación NO honra DATABASE_URL. Se está sembrando en SU base "
                      "de datos, no en una temporal. Eso es un hallazgo, y conviene arreglarlo "
                      "antes de sembrar 2000 pólizas ahí.")
            for endpoint in ENDPOINTS:
                ruta = endpoint.replace("{id}", str(primer_id))
                cliente.get(ruta)                        # calentamiento
                contador["n"] = 0
                t0 = time.perf_counter()
                r = cliente.get(ruta)
                dt = (time.perf_counter() - t0) * 1000
                if r.status_code >= 400:
                    raise SystemExit(f"\n{ruta} devolvió {r.status_code}. No se escribe el CSV: primero hay "
                                     f"que dejar el servicio respondiendo. Cuerpo: {r.text[:300]}")
                fila = {"endpoint": endpoint, "estrategia": ESTRATEGIAS[endpoint], "n_polizas": n,
                        "consultas_sql": contador["n"], "tiempo_ms": round(dt, 1)}
                filas.append(fila)
                print(f"  {endpoint:<16} n={n:<5} consultas {fila['consultas_sql']:>5}   "
                      f"{fila['tiempo_ms']:>8.1f} ms")

    # La conexión global de la aplicación apunta a esta base temporal; cerrarla
    # antes de borrar el directorio evita dejar el archivo bloqueado en Windows.
    from database import engine
    engine.dispose()
    temporal.cleanup()

    with open(a.salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    print(f"\n{a.salida} escrito con {len(filas)} filas. Base temporal: {db}")


if __name__ == "__main__":
    main()
