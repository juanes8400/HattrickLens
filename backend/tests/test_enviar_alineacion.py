"""Enviar la alineación desde Alineación (2026-11-19).

Lo que se vigila: que el primer paso sólo PREVÉ, que el segundo envía y
comprueba releyendo, que lo elegido (táctica, capitán, tiro libre, penales)
viaja y lo demás del usuario se conserva, y que un cambio programado que ya no
tiene sentido se quita y se dice."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.analysis import enviar as modulo
from app.api.v1.endpoints.analysis.alineacion import _roles_del_once
from app.api.v1.endpoints.analysis.enviar import EnvioDeAlineacion, _cambios_que_valen
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

PARTIDO = 990001


class HattrickDePrueba:
    """Guarda lo que se le manda y contesta como Hattrick."""

    enviados: list[dict[str, Any]] = []
    guardado: list[int] = []

    def __init__(self, *_a: Any) -> None:
        pass

    async def fetch(self, file: str, **params: Any) -> dict[str, Any]:
        assert params["actionType"] == "view"
        if HattrickDePrueba.guardado:
            return {
                "available": True,
                "positions": [{"ht_player_id": i} for i in HattrickDePrueba.guardado],
            }
        return {
            "available": True,
            "positions": [{"ht_player_id": 1}],
            "tactic_type": 2,
            "attitude": 1,
            "coach_modifier": -3,
            # Un cambio con alguien que no está en la plantilla: hay que quitarlo.
            "substitutions": [{"playerin": 123456789, "playerout": 987654321, "orderType": 1}],
        }

    async def alineacion(
        self, match: int, team: int, payload: dict, *, guardar: bool, **kw: Any
    ) -> dict:
        HattrickDePrueba.enviados.append({"guardar": guardar, "payload": payload})
        if guardar:
            HattrickDePrueba.guardado = [r["id"] for r in payload["positions"] if r["id"]]
            return {"orders_set": True, "reason": ""}
        return {
            "prediction": {
                "ratings": {
                    "midfield": 30,
                    "right_def": 72,
                    "central_def": 82,
                    "left_def": 72,
                    "right_att": 41,
                    "central_att": 47,
                    "left_att": 52,
                }
            }
        }

    async def aclose(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _hattrick(monkeypatch: pytest.MonkeyPatch) -> None:
    HattrickDePrueba.enviados = []
    HattrickDePrueba.guardado = []
    monkeypatch.setattr(modulo, "CHPPClient", HattrickDePrueba)
    monkeypatch.setattr(modulo, "decrypt_token", lambda t: t)


async def _escenario() -> tuple[Any, int]:
    factory, team_id = await seeded_session()
    async with factory() as s:
        team = await s.get(m.Team, team_id)
        team.owner_user_id = 1
        s.add(
            m.CHPPToken(
                user_id=1,
                oauth_token_enc=b"falso",  # noqa: S106, prueba
                oauth_secret_enc=b"falso",  # noqa: S106, prueba
                status="active",
            )
        )
        s.add(
            m.Match(
                ht_match_id=PARTIDO,
                played_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=2),
                match_type=1,
                status="UPCOMING",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=1,
                home_team_name="Pulgas Arrechas",
                away_team_name="Rival",
            )
        )
        await s.commit()
    return factory, team_id


def _mandar(envio: dict[str, Any]) -> dict[str, Any]:
    async def correr() -> dict[str, Any]:
        factory, team_id = await _escenario()
        async with factory() as s:
            from app.api.v1.endpoints.analysis.alineacion import _lineup_sin_cache

            once = await _lineup_sin_cache(
                team_id,
                formation=None,
                central_defenders=None,
                inner_midfielders=None,
                orders=None,
                exclude=None,
                session=s,
                entrenando=False,
            )
            titulares = [f["htPlayerId"] for f in once["lineup"]]
            datos = {"htMatchId": PARTIDO, **envio}
            datos = {
                k: (titulares[v] if isinstance(v, int) and k in ("capitan", "tiroLibre") else v)
                for k, v in datos.items()
            }
            if "penales" in datos:
                datos["penales"] = [titulares[i] for i in datos["penales"]]
            out = await modulo.enviar_alineacion(
                team_id, EnvioDeAlineacion(**datos), s, SimpleNamespace(id=1)
            )
            out["_titulares"] = titulares
            return out

    return asyncio.run(correr())


def test_el_primer_paso_solo_preve() -> None:
    out = _mandar({"tactica": 1, "capitan": 3, "tiroLibre": 5, "penales": [5, 3]})
    assert out["prediccion"]["central_def"] == 82
    assert out["guardada"] is False and out["confirmada"] is False
    [envio] = HattrickDePrueba.enviados
    assert envio["guardar"] is False
    payload = envio["payload"]
    titulares = out["_titulares"]
    assert payload["settings"]["tactic"] == 1
    assert payload["captain"] == titulares[3]
    assert payload["setPieces"] == titulares[5]
    assert [k["id"] for k in payload["kickers"][:2]] == [titulares[5], titulares[3]]
    # Lo del usuario que la app no propone, intacto.
    assert payload["settings"]["speechLevel"] == 1
    assert payload["settings"]["coachModifier"] == -3
    # Había órdenes: se avisa de que se sustituyen.
    assert out["habiaOrdenes"] is True and out["tacticaPrevia"] == 2


def test_el_cambio_con_un_jugador_que_no_esta_se_quita_y_se_dice() -> None:
    out = _mandar({})
    assert out["cambiosQuitados"] == 1
    assert HattrickDePrueba.enviados[0]["payload"]["substitutions"] == []


def test_enviar_guarda_y_lo_comprueba_releyendo() -> None:
    out = _mandar({"guardar": True})
    assert HattrickDePrueba.enviados[0]["guardar"] is True
    assert out["guardada"] is True and out["confirmada"] is True


def test_un_capitan_que_no_juega_se_rechaza_antes_de_llamar() -> None:
    async def correr() -> None:
        factory, team_id = await _escenario()
        async with factory() as s:
            await modulo.enviar_alineacion(
                team_id,
                EnvioDeAlineacion(htMatchId=PARTIDO, capitan=123456789),
                s,
                SimpleNamespace(id=1),
            )

    with pytest.raises(HTTPException) as exc2:
        asyncio.run(correr())
    assert exc2.value.status_code == 422
    assert HattrickDePrueba.enviados == []


def test_cambios_que_valen() -> None:
    cambios = [
        {"playerin": 1, "playerout": 2},
        {"playerin": 3, "playerout": 99},
        {"playerin": 0, "playerout": 2},
    ]
    validos, quitados = _cambios_que_valen(cambios, {1, 2, 3})
    assert validos == [cambios[0], cambios[2]] and quitados == 1


def test_roles_se_sugieren_entre_los_once() -> None:
    jugadores = [
        {
            "ht_player_id": 1,
            "name": "A",
            "leadership": 7,
            "experience": 8,
            "skills": {"set_pieces": 3, "scoring": 2},
        },
        {
            "ht_player_id": 2,
            "name": "B",
            "leadership": 2,
            "experience": 3,
            "skills": {"set_pieces": 12, "scoring": 9},
        },
    ]
    roles = _roles_del_once(jugadores)
    assert roles["captain"]["htPlayerId"] == 1
    assert roles["setPieces"]["htPlayerId"] == 2
    assert [p["htPlayerId"] for p in roles["penaltyTakers"]] == [2, 1]


def test_si_hattrick_niega_el_envio_dice_que_permisos_tiene_y_nunca_es_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-11-19: tras reconectar seguía saliendo «falta el permiso». El error
    trae lo que Hattrick dice que tiene el acceso, y nunca es un 401: ante un
    401 el navegador repite la petición sola, y con un envío eso sería mandar
    la alineación dos veces."""
    from app.infrastructure.chpp.client import CHPPAuthError, CHPPDeniedError

    async def negado(self: Any, *a: Any, guardar: bool, **kw: Any) -> dict:
        raise CHPPDeniedError("Hattrick no deja enviar la alineación con este acceso")

    async def permisos(self: Any) -> list[str]:
        return ["manage_youthplayers"]

    monkeypatch.setattr(HattrickDePrueba, "alineacion", negado)
    monkeypatch.setattr(HattrickDePrueba, "permisos", permisos, raising=False)
    with pytest.raises(HTTPException) as exc:
        _mandar({"guardar": True})
    assert exc.value.status_code == 403
    assert "manage_youthplayers" in str(exc.value.detail)

    async def muerto(self: Any, *a: Any, guardar: bool, **kw: Any) -> dict:
        raise CHPPAuthError("token revocado")

    monkeypatch.setattr(HattrickDePrueba, "alineacion", muerto)
    with pytest.raises(HTTPException) as exc2:
        _mandar({"guardar": True})
    assert exc2.value.status_code == 409
