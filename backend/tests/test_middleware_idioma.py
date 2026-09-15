"""El middleware traduce en inglés y marca Vary en los dos idiomas."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.i18n.middleware import TraducirRespuestas, _con_vary


def _cliente() -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/prueba")
    def prueba() -> dict[str, str]:
        return {"message": "Los datos no se sincronizan hace más de 12 horas.", "key": "Lesión"}

    app.add_middleware(TraducirRespuestas)
    return TestClient(app)


def test_ingles_traducido_y_claves_intactas() -> None:
    r = _cliente().get("/api/v1/prueba", headers={"Accept-Language": "en"})
    assert r.json() == {
        "message": "Data hasn't been synced for more than 12 hours.",
        "key": "Lesión",
    }
    assert "Accept-Language" in r.headers["vary"]


def test_espanol_intacto_pero_con_vary() -> None:
    r = _cliente().get("/api/v1/prueba", headers={"Accept-Language": "es"})
    assert r.json()["message"] == "Los datos no se sincronizan hace más de 12 horas."
    assert "Accept-Language" in r.headers["vary"]


def test_vary_conserva_lo_que_traia() -> None:
    cabeceras = _con_vary([(b"vary", b"Origin"), (b"content-type", b"application/json")])
    assert (b"vary", b"Origin, Accept-Language") in cabeceras
    assert _con_vary([(b"vary", b"accept-language")]) == [(b"vary", b"accept-language")]
