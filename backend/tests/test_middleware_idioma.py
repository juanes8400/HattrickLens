"""El middleware traduce en inglés y marca Vary en los dos idiomas."""

import json
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app.domain.value_objects.formatting import thousands
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


def test_stream_ndjson_se_traduce_linea_a_linea() -> None:
    app = FastAPI()

    @app.post("/api/v1/stream")
    def stream() -> StreamingResponse:
        def generar() -> Iterator[bytes]:
            yield b'{"type":"progress","message":"Revisando tus compras y ventas..."}\n'
            yield b'{"type":"error","message":"Hattrick no responde: tiempo"}\n'

        return StreamingResponse(generar(), media_type="application/x-ndjson")

    app.add_middleware(TraducirRespuestas)
    r = TestClient(app).post("/api/v1/stream", headers={"Accept-Language": "en"})
    lineas = [json.loads(x) for x in r.text.strip().split("\n")]
    assert lineas == [
        {"type": "progress", "message": "Checking your purchases and sales..."},
        {"type": "error", "message": "Hattrick isn't responding: tiempo"},
    ]


def test_vary_conserva_lo_que_traia() -> None:
    cabeceras = _con_vary([(b"vary", b"Origin"), (b"content-type", b"application/json")])
    assert (b"vary", b"Origin, Accept-Language") in cabeceras
    assert _con_vary([(b"vary", b"accept-language")]) == [(b"vary", b"accept-language")]


def test_los_numeros_los_escribe_el_idioma_de_la_peticion() -> None:
    """El texto se traduce al salir, pero los números ya venían escritos."""
    app = FastAPI()

    @app.get("/api/v1/numero")
    def numero() -> dict[str, str]:
        return {"message": thousands(9870896)}

    app.add_middleware(TraducirRespuestas)
    cliente = TestClient(app)
    assert cliente.get("/api/v1/numero", headers={"Accept-Language": "en"}).json() == {
        "message": "9,870,896"
    }
    assert cliente.get("/api/v1/numero", headers={"Accept-Language": "es"}).json() == {
        "message": "9.870.896"
    }
