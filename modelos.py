"""Tablas del servicio (SQLAlchemy 2.0, estilo declarativo tipado)."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Poliza(Base):
    __tablename__ = "polizas"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    asegurado: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(10))
    prima: Mapped[float] = mapped_column(Float)
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_fin: Mapped[date] = mapped_column(Date)
    # Interno: nunca sale en una respuesta (los esquemas de salida no lo declaran).
    token_firma: Mapped[str] = mapped_column(String(64))

    # La carga por defecto es perezosa ("select"); cada endpoint elige su
    # estrategia en la consulta (ver Parte C en HALLAZGOS.md).
    siniestros: Mapped[list["Siniestro"]] = relationship(
        back_populates="poliza", cascade="all, delete-orphan", order_by="Siniestro.id")
    predicciones: Mapped[list["Prediccion"]] = relationship(
        back_populates="poliza", cascade="all, delete-orphan")


class Siniestro(Base):
    __tablename__ = "siniestros"

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[float] = mapped_column(Float)
    descripcion: Mapped[str] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(10), default="abierto")

    poliza: Mapped["Poliza"] = relationship(back_populates="siniestros")

    @property
    def numero_poliza(self) -> str:
        return self.poliza.numero


class Prediccion(Base):
    __tablename__ = "predicciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"), index=True)
    puntaje: Mapped[float] = mapped_column(Float)
    alto_riesgo: Mapped[bool]
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    poliza: Mapped["Poliza"] = relationship(back_populates="predicciones")
