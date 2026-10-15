"""Conexión a la base de datos: un motor por proceso, una sesión por petición."""
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    pass


def crear_motor(url: str) -> Engine:
    """Motor para `url`. En SQLite activa las claves foráneas, que vienen apagadas
    por defecto, en cada conexión nueva (M9 · 7)."""
    es_sqlite = url.startswith("sqlite")
    motor = create_engine(url, connect_args={"check_same_thread": False} if es_sqlite else {})
    if es_sqlite:
        @event.listens_for(motor, "connect")
        def _activar_fk(conexion_dbapi, _registro):
            cursor = conexion_dbapi.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return motor


engine = crear_motor(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión para la petición y la cierra al
    terminar, haya ido bien o no. Lo que no se confirmó con `commit` se descarta."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
