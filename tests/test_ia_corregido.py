"""
Corrección de `ia_tests_propuesta.py` (Parte D; el dictamen está en DICTAMEN_IA.md).

Lo que cambia respecto de la propuesta de la IA:
  1. Cada test afirma UN resultado exacto (código y contenido). Ninguno acepta
     «200 o 404» ni «< 500»: un test que admite todos los resultados no puede fallar.
  2. El aislamiento es real: la fixture `cliente` (conftest.py) sustituye
     `database.get_db` —la dependencia que la app usa de verdad— por sesiones
     sobre una base temporal. Y lo que un test dice probar, lo comprueba: crear
     es poder volver a leer; puntuar es quedar registrado.
  3. Los datos variados son deterministas: `parametrize` con casos fijos, sin
     `random`. El mismo commit da siempre el mismo resultado.

    pytest tests/test_ia_corregido.py -v
"""
import pytest

from config import get_settings

SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000, "descripcion": "Choque leve", "estado": "abierto"}


# --- Creación: 201, y lo creado se puede volver a leer -------------------------

@pytest.mark.parametrize("tipo", ["auto", "hogar", "vida"])
@pytest.mark.parametrize("prima", [0.01, 1_250_000, 4_999_999.99, 50_000_000])
def test_crear_poliza_devuelve_201_y_persiste(cliente, poliza_valida, tipo, prima):
    datos = poliza_valida(tipo=tipo, prima=prima)
    r = cliente.post("/polizas", json=datos)
    assert r.status_code == 201
    creada = r.json()
    for campo in ("numero", "asegurado", "tipo", "prima", "fecha_inicio", "fecha_fin"):
        assert creada[campo] == datos[campo]
    leida = cliente.get(f"/polizas/{creada['id']}")
    assert leida.status_code == 200
    assert leida.json() == creada


def test_crear_poliza_con_siniestros_anidados_los_persiste(cliente, poliza_valida):
    r = cliente.post("/polizas", json=poliza_valida(siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000}]))
    assert r.status_code == 201
    leida = cliente.get(f"/polizas/{r.json()['id']}").json()
    assert [s["monto"] for s in leida["siniestros"]] == [850_000, 150_000]


def test_numero_duplicado_da_409_y_no_duplica(cliente, poliza_valida):
    datos = poliza_valida()
    assert cliente.post("/polizas", json=datos).status_code == 201
    assert cliente.post("/polizas", json=datos).status_code == 409
    assert [p["numero"] for p in cliente.get("/polizas").json()] == [datos["numero"]]


# --- Recursos inexistentes: 404 exacto, en cada ruta ----------------------------

@pytest.mark.parametrize("metodo, ruta, cuerpo", [
    ("get", "/polizas/999999", None),
    ("put", "/polizas/999999", {"prima": 10}),
    ("post", "/polizas/999999/siniestros", SINIESTRO),
    ("post", "/score", {"numero": "POL-NO-EXISTE"}),
])
def test_recurso_inexistente_da_404(cliente, metodo, ruta, cuerpo):
    r = getattr(cliente, metodo)(ruta, **({"json": cuerpo} if cuerpo else {}))
    assert r.status_code == 404


def test_siniestro_de_poliza_inexistente_no_se_guarda(cliente):
    cliente.post("/polizas/999999/siniestros", json=SINIESTRO)
    assert cliente.get("/siniestros").json() == []


# --- Actualización: parcial y persistente ---------------------------------------

def test_put_parcial_cambia_solo_lo_enviado_y_persiste(cliente, poliza_valida):
    creada = cliente.post("/polizas", json=poliza_valida(asegurado="Bruno Celis", tipo="hogar")).json()
    r = cliente.put(f"/polizas/{creada['id']}", json={"prima": 999_000})
    assert r.status_code == 200
    leida = cliente.get(f"/polizas/{creada['id']}").json()
    assert leida == {**creada, "prima": 999_000}


def test_declarar_siniestro_da_201_y_persiste(cliente, poliza_valida):
    creada = cliente.post("/polizas", json=poliza_valida()).json()
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201
    leida = cliente.get(f"/polizas/{creada['id']}").json()
    assert [s["id"] for s in leida["siniestros"]] == [r.json()["id"]]


# --- Validación: lo inválido da 422 y no se guarda -------------------------------

@pytest.mark.parametrize("cambio", [
    {"prima": 0},
    {"prima": -1},
    {"tipo": "barco"},
    {"asegurado": "Al"},
    {"fecha_inicio": "2027-01-14", "fecha_fin": "2026-01-15"},
    {"fecha_inicio": "2026-01-15", "fecha_fin": "2026-01-15"},
    {"siniestros": [{**SINIESTRO, "monto": -50}]},
    {"siniestros": [{**SINIESTRO, "descripcion": "x"}]},
])
def test_entrada_invalida_da_422_y_no_se_guarda(cliente, poliza_valida, cambio):
    r = cliente.post("/polizas", json=poliza_valida(**cambio))
    assert r.status_code == 422
    assert cliente.get("/polizas").json() == []


@pytest.mark.parametrize("cuerpo", [{"prima": 0}, {"asegurado": None}, {"fecha_fin": "2025-01-01"}])
def test_put_invalido_da_422_y_no_cambia_nada(cliente, poliza_valida, cuerpo):
    creada = cliente.post("/polizas", json=poliza_valida()).json()
    assert cliente.put(f"/polizas/{creada['id']}", json=cuerpo).status_code == 422
    assert cliente.get(f"/polizas/{creada['id']}").json() == creada


@pytest.mark.parametrize("entrada, esperado", [
    ("Carla Ibáñez", "Carla Ibáñez"),
    ("  ana    rueda ", "Ana Rueda"),
])
def test_el_asegurado_se_normaliza_y_no_se_pierde(cliente, poliza_valida, entrada, esperado):
    r = cliente.post("/polizas", json=poliza_valida(asegurado=entrada))
    assert r.status_code == 201
    assert r.json()["asegurado"] == esperado


# --- Lecturas con relaciones -----------------------------------------------------

def test_resumen_cuenta_y_suma_por_poliza(cliente, poliza_valida):
    con = poliza_valida(siniestros=[SINIESTRO, {**SINIESTRO, "monto": 150_000.5}])
    sin = poliza_valida()
    cliente.post("/polizas", json=con)
    cliente.post("/polizas", json=sin)
    r = cliente.get("/resumen")
    assert r.status_code == 200
    assert r.json() == [
        {"numero": con["numero"], "n_siniestros": 2, "monto_total": 1_000_000.5},
        {"numero": sin["numero"], "n_siniestros": 0, "monto_total": 0.0},
    ]


def test_listado_trae_cada_poliza_con_sus_siniestros(cliente, poliza_valida):
    a = cliente.post("/polizas", json=poliza_valida(siniestros=[SINIESTRO])).json()
    b = cliente.post("/polizas", json=poliza_valida()).json()
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert r.json() == [a, b]


# --- Puntuación: responde y queda registrada --------------------------------------

def test_score_de_poliza_recien_creada_queda_registrado(cliente, poliza_valida):
    datos = poliza_valida(siniestros=[SINIESTRO])
    assert cliente.post("/polizas", json=datos).status_code == 201
    r = cliente.post("/score", json={"numero": datos["numero"]})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["numero"] == datos["numero"]
    assert 0.0 <= cuerpo["puntaje"] <= 1.0
    assert cuerpo["alto_riesgo"] == (cuerpo["puntaje"] > get_settings().umbral_alto_riesgo)
    registradas = cliente.get("/predicciones").json()
    assert [(p["numero"], round(p["puntaje"], 4)) for p in registradas] == [(datos["numero"], cuerpo["puntaje"])]
