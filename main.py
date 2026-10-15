"""
polizas-api — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás · prototipo interno.

El esquema de la base lo crea Alembic (`alembic upgrade head`), no el arranque.
"""
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from config import Settings, get_settings
from database import get_db
from esquemas import (PolizaActualizacion, PolizaEntrada, PolizaSalida, PrediccionSalida,
                      PuntuacionEntrada, PuntuacionSalida, ResumenPoliza, Salud,
                      SiniestroConPoliza, SiniestroEntrada, SiniestroSalida)
from modelos import Poliza, Prediccion, Siniestro
from servicios import firmar, get_modelo, puntuar, resumen_cartera

app = FastAPI(title="Pólizas API", version="1.0.0")


def _poliza_o_404(db: Session, id_poliza: int) -> Poliza:
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la póliza {id_poliza}")
    return poliza


@app.get("/health", response_model=Salud)
def salud(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"estado": "ok", "base_de_datos": True}
    except SQLAlchemyError:
        return {"estado": "degradado", "base_de_datos": False}


@app.post("/polizas", response_model=PolizaSalida, status_code=status.HTTP_201_CREATED)
def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db),
                 settings: Settings = Depends(get_settings)):
    poliza = Poliza(**datos.model_dump(exclude={"siniestros"}),
                    token_firma=firmar(datos.numero, settings.secreto_firma))
    poliza.siniestros = [Siniestro(**s.model_dump()) for s in datos.siniestros]
    db.add(poliza)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"ya existe la póliza {datos.numero}")
    return poliza


# Parte C · selectinload: una consulta para las pólizas y otra (IN por lotes)
# para todos sus siniestros, sin repetir las columnas de la póliza por siniestro.
@app.get("/polizas", response_model=list[PolizaSalida])
def listar_polizas(db: Session = Depends(get_db)):
    consulta = select(Poliza).options(selectinload(Poliza.siniestros)).order_by(Poliza.id)
    return db.scalars(consulta).all()


# Parte C · lazy: es una sola póliza; sus siniestros se piden al serializar con
# una segunda consulta. Cargarlos «de una vez» no ahorra nada (ver CONSULTAS.csv).
@app.get("/polizas/{id_poliza}", response_model=PolizaSalida)
def obtener_poliza(id_poliza: int, db: Session = Depends(get_db)):
    return _poliza_o_404(db, id_poliza)


@app.put("/polizas/{id_poliza}", response_model=PolizaSalida)
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion, db: Session = Depends(get_db)):
    poliza = _poliza_o_404(db, id_poliza)
    cambios = datos.model_dump(exclude_unset=True)
    fecha_fin = cambios.get("fecha_fin", poliza.fecha_fin)
    if fecha_fin <= poliza.fecha_inicio:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "fecha_fin debe ser posterior a fecha_inicio")
    for campo, valor in cambios.items():
        setattr(poliza, campo, valor)
    db.commit()
    return poliza


@app.post("/polizas/{id_poliza}/siniestros", response_model=SiniestroSalida,
          status_code=status.HTTP_201_CREATED)
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada, db: Session = Depends(get_db)):
    poliza = _poliza_o_404(db, id_poliza)
    siniestro = Siniestro(poliza_id=poliza.id, **datos.model_dump())
    db.add(siniestro)
    db.commit()
    return siniestro


# Parte C · joinedload: relación muchos-a-uno; cada fila de siniestros trae su
# póliza en el mismo JOIN, sin multiplicar filas.
@app.get("/siniestros", response_model=list[SiniestroConPoliza])
def listar_siniestros(db: Session = Depends(get_db)):
    consulta = select(Siniestro).options(joinedload(Siniestro.poliza)).order_by(Siniestro.id)
    return db.scalars(consulta).all()


# Parte C · agregada: COUNT y SUM en la base; no se carga ningún siniestro.
@app.get("/resumen", response_model=list[ResumenPoliza])
def resumen(db: Session = Depends(get_db)):
    return resumen_cartera(db)


@app.post("/score", response_model=PuntuacionSalida)
def puntuar_poliza(datos: PuntuacionEntrada, db: Session = Depends(get_db),
                   settings: Settings = Depends(get_settings), modelo=Depends(get_modelo)):
    poliza = db.scalar(select(Poliza).where(Poliza.numero == datos.numero))
    if poliza is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la póliza {datos.numero}")
    prediccion = puntuar(db, poliza, modelo, settings)
    db.commit()
    return {"numero": poliza.numero, "puntaje": round(prediccion.puntaje, 4),
            "alto_riesgo": prediccion.alto_riesgo}


@app.get("/predicciones", response_model=list[PrediccionSalida])
def listar_predicciones(db: Session = Depends(get_db)):
    consulta = (select(Prediccion.id, Prediccion.poliza_id, Poliza.numero, Prediccion.puntaje,
                       Prediccion.alto_riesgo, Prediccion.creado_en)
                .join(Poliza, Prediccion.poliza_id == Poliza.id)
                .order_by(Prediccion.id))
    return db.execute(consulta).all()
