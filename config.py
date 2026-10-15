"""Configuración del servicio, leída del entorno y de `.env` (M8 · 3).

Nada sensible vive en el código: los valores reales se ponen en `.env` (que no
se versiona) o en variables de entorno del contenedor. `.env.example` documenta
las claves con valores de ejemplo con los que el servicio arranca.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Cada campo se lee de la variable homónima en mayúsculas: DATABASE_URL, etc.
    database_url: str = "sqlite:///app.db"
    ruta_modelo: str = "modelo.pkl"
    umbral_alto_riesgo: float = Field(default=0.6, ge=0, le=1)
    # Sin valor real por defecto: el de producción se inyecta por entorno.
    secreto_firma: str = Field(default="solo-desarrollo-cambiar", min_length=8)
    clave_api_reaseguro: str = ""


@lru_cache
def get_settings() -> Settings:
    """Una sola instancia por proceso; se inyecta con `Depends(get_settings)`."""
    return Settings()
