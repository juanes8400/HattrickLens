"""Lo que lleva huella se guarda un año; el index se pregunta siempre.

MEDIDO en producción el 2026-11-10: `/assets/index-Da-mziAK.js` salía sin
`Cache-Control` y, pedido con `If-None-Match` igual a su propia etag, volvía
entero con un 200. Cada visita se bajaba la aplicación completa.

La carpeta `backend/static` sólo existe dentro de la imagen de Docker, así que
aquí se monta una de mentira con la misma forma que deja `vite build`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import CACHE_CON_HUELLA, CACHE_DEL_INDEX, montar_frontend

BUNDLE = "/assets/index-Da-mziAK.js"


@pytest.fixture
def cliente(tmp_path: Path) -> TestClient:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-Da-mziAK.js").write_text("console.log(1);")
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>")
    (tmp_path / "favicon.svg").write_text("<svg/>")

    app = FastAPI()

    # Como en `app.main`: la API se declara antes y el frontend va lo último.
    @app.get("/api/v1/eco")
    async def eco() -> dict[str, str]:
        return {"eco": "eco"}

    montar_frontend(app, tmp_path)
    return TestClient(app)


def test_los_valores_son_los_acordados() -> None:
    assert CACHE_CON_HUELLA == "public, max-age=31536000, immutable"
    assert CACHE_DEL_INDEX == "no-cache"


def test_el_bundle_con_huella_se_guarda_un_ano(cliente: TestClient) -> None:
    r = cliente.get(BUNDLE)
    assert r.status_code == 200
    assert r.text == "console.log(1);"
    assert r.headers["cache-control"] == CACHE_CON_HUELLA


def test_el_bundle_contesta_304_a_quien_ya_lo_tiene(cliente: TestClient) -> None:
    # Lo que fallaba en producción: la comodín iba registrada antes que el
    # montaje de `/assets` y servía ella los bundles, sin saber de etags.
    etag = cliente.get(BUNDLE).headers["etag"]
    r = cliente.get(BUNDLE, headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["cache-control"] == CACHE_CON_HUELLA


def test_un_bundle_que_no_existe_no_se_guarda(cliente: TestClient) -> None:
    # Tras un despliegue, quien tenga la página vieja abierta pedirá trozos que
    # ya no están. Un 404 a secas: ni el index disfrazado de JavaScript ni una
    # respuesta que el navegador pueda quedarse un año.
    r = cliente.get("/assets/index-YaNoEstoy.js")
    assert r.status_code == 404
    assert "cache-control" not in r.headers


@pytest.mark.parametrize("ruta", ["/", "/index.html", "/rivals/277186"])
def test_el_index_se_pregunta_siempre(cliente: TestClient, ruta: str) -> None:
    r = cliente.get(ruta)
    assert r.status_code == 200
    assert "id=root" in r.text
    assert r.headers["cache-control"] == CACHE_DEL_INDEX


def test_la_api_no_se_toca(cliente: TestClient) -> None:
    r = cliente.get("/api/v1/eco")
    assert r.json() == {"eco": "eco"}
    assert "cache-control" not in r.headers


def test_lo_suelto_de_la_raiz_se_queda_como_estaba(cliente: TestClient) -> None:
    r = cliente.get("/favicon.svg")
    assert r.status_code == 200
    assert r.text == "<svg/>"
    assert "cache-control" not in r.headers
