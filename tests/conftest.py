"""Fixtures compartidas de los tests propios (M10 · 6).

Aislamiento: cada test recibe un `cliente` cuya dependencia `database.get_db`
está sustituida con `app.dependency_overrides` por sesiones sobre una base
SQLite TEMPORAL, nueva para ese test. La base de la aplicación no se toca.

Cada petición abre su propia sesión, igual que en producción: si una ruta
olvida el `commit`, la petición siguiente no ve el dato y el test lo nota.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
# Red de seguridad: si algo usara el motor de la aplicación, caería en una base
# desechable y no en app.db. Se fija antes de importar la aplicación.
os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.mkdtemp(prefix='polizas-tests-')) / 'nunca.db'}"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database import Base, crear_motor, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def cliente(tmp_path):
    motor = crear_motor(f"sqlite:///{tmp_path / 'prueba.db'}")
    Base.metadata.create_all(motor)
    Sesion = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    previo = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        if previo is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previo
        motor.dispose()


@pytest.fixture
def poliza_valida():
    """Fábrica de pólizas válidas y deterministas: el número sale de un contador."""
    contador = iter(range(1, 10_000))

    def _fabricar(**extra) -> dict:
        datos = {
            "numero": f"POL-T-{next(contador):05d}",
            "asegurado": "Ana Rueda",
            "tipo": "auto",
            "prima": 1_250_000,
            "fecha_inicio": "2026-01-15",
            "fecha_fin": "2027-01-14",
        }
        datos.update(extra)
        return datos

    return _fabricar
