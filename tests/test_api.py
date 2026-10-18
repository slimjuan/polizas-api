"""Pruebas básicas del servicio, aisladas en una base temporal (ver conftest.py).

    pytest tests/test_api.py
"""


def test_health_indica_que_la_base_responde(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "base_de_datos": True}


def test_health_indica_degradado_si_la_base_no_responde(cliente, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    def fallar_consulta(self, *args, **kwargs):
        raise SQLAlchemyError("base de datos no disponible")

    monkeypatch.setattr(Session, "execute", fallar_consulta)

    r = cliente.get("/health")

    assert r.status_code == 200
    assert r.json() == {"estado": "degradado", "base_de_datos": False}


def test_crear_poliza(cliente, poliza_valida):
    datos = poliza_valida()
    r = cliente.post("/polizas", json=datos)
    assert r.status_code == 201
    assert r.json()["numero"] == datos["numero"]
    assert "token_firma" not in r.json()


def test_listar_polizas(cliente, poliza_valida):
    datos = poliza_valida()
    cliente.post("/polizas", json=datos)
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert [p["numero"] for p in r.json()] == [datos["numero"]]


def test_siniestros_traen_el_numero_de_su_poliza(cliente, poliza_valida):
    creada = cliente.post("/polizas", json=poliza_valida()).json()
    cliente.post(f"/polizas/{creada['id']}/siniestros",
                 json={"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve"})
    r = cliente.get("/siniestros")
    assert r.status_code == 200
    assert r.json()[0]["numero_poliza"] == creada["numero"]


def test_resumen_vacio(cliente):
    r = cliente.get("/resumen")

    assert r.status_code == 200
    assert r.json() == []


def test_predicciones_vacias(cliente):
    r = cliente.get("/predicciones")

    assert r.status_code == 200
    assert r.json() == []
