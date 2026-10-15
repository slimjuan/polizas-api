"""Lógica de negocio: firma, puntuación de riesgo y resumen de cartera.

Vive aparte de las rutas para que `main.py` solo traduzca HTTP <-> dominio, y
para que cada pieza se pueda probar sin levantar la aplicación.
"""
import hashlib
import pickle
from datetime import date
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import Settings, get_settings
from modelos import Poliza, Prediccion, Siniestro


def firmar(numero: str, secreto: str) -> str:
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


@lru_cache
def get_modelo():
    """El modelo se deserializa una vez por proceso, la primera vez que se pide."""
    with open(get_settings().ruta_modelo, "rb") as fh:
        return pickle.load(fh)


def rasgos(db: Session, poliza: Poliza) -> list[float]:
    """Prima, número y monto de siniestros, y antigüedad en días.
    Cuenta y suma en la base (una consulta) en vez de cargar los siniestros."""
    n, total = db.execute(
        select(func.count(Siniestro.id), func.coalesce(func.sum(Siniestro.monto), 0.0))
        .where(Siniestro.poliza_id == poliza.id)
    ).one()
    return [poliza.prima, n, total, (date.today() - poliza.fecha_inicio).days]


def puntuar(db: Session, poliza: Poliza, modelo, settings: Settings) -> Prediccion:
    """Calcula el puntaje y lo deja registrado en la sesión (sin confirmar)."""
    puntaje = float(modelo.predict_proba([rasgos(db, poliza)])[0][1])
    prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje,
                            alto_riesgo=puntaje > settings.umbral_alto_riesgo)
    db.add(prediccion)
    return prediccion


def resumen_cartera(db: Session) -> list[dict]:
    """Por póliza, cuántos siniestros tiene y cuánto suman: una sola consulta
    agregada (LEFT JOIN + GROUP BY); ningún siniestro viaja a Python."""
    filas = db.execute(
        select(Poliza.numero,
               func.count(Siniestro.id).label("n_siniestros"),
               func.coalesce(func.sum(Siniestro.monto), 0.0).label("monto_total"))
        .outerjoin(Siniestro, Siniestro.poliza_id == Poliza.id)
        .group_by(Poliza.id)
        .order_by(Poliza.id)
    )
    return [{"numero": f.numero, "n_siniestros": f.n_siniestros,
             "monto_total": round(f.monto_total, 2)} for f in filas]
