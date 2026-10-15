"""Entorno de Alembic. La URL sale de la misma configuración que la aplicación
(`DATABASE_URL`, vía config.get_settings), así migración y servicio apuntan
siempre a la misma base."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

import modelos  # noqa: F401  registra las tablas en Base.metadata
from config import get_settings
from database import Base, crear_motor

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
URL = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    motor = crear_motor(URL)
    with motor.connect() as connection:
        # render_as_batch: SQLite no soporta ALTER TABLE completo.
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
