"""Enviar la alineación a Hattrick desde Alineación (2026-11-19).

Pedido del usuario: «deberíamos poder enviar alineación desde Alineación», y
con ella táctica, capitán, tiro libre y lanzadores de penales. Vuelve lo que se
construyó el 2026-09-19 (commit 2c07e14) y se retiró al día siguiente.

VA EN DOS TIEMPOS, y es la regla que más importa:

* `guardar=false` pide a Hattrick la PREVISIÓN de esa alineación. Hattrick la
  lee entera, contesta los siete ratings y no guarda nada.
* `guardar=true` la ENVÍA y sustituye las órdenes de ese partido. Después se
  vuelven a leer las órdenes para comprobar que quedaron como se mandaron.

Nada de esto se hace solo: ni desde la sincronización ni desde una alerta.
Sólo desde el botón, y el segundo paso lo confirma el usuario.

Lo que la app no propone --actitud, estilo del entrenador, marcaje y cambios
programados-- se lee de las órdenes actuales y se devuelve tal cual. Un cambio
programado que nombra a alguien que ya no está en el once ni en el banquillo
se quita, porque Hattrick rechazaría el envío entero, y se dice.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_team_owner
from app.api.rate_limit import limite
from app.application.commands.sync_team.comun import FILE_VERSIONS
from app.application.queries.mejor_alineacion import SECTORES_PREVISTOS
from app.application.queries.nombre_del_torneo import nombre_del_torneo, nombres_de_copa
from app.domain.value_objects.alineacion_para_hattrick import (
    AlineacionInvalidaError,
    alineacion_para_hattrick,
)
from app.domain.value_objects.ht_constants import (
    NON_OFFICIAL_MATCH_TYPES,
    TACTIC_TYPES,
)
from app.infrastructure.chpp.client import (
    CHPPAuthError,
    CHPPClient,
    CHPPDeniedError,
    CHPPUnavailableError,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import decrypt_token

router = APIRouter()

#: Cuántos partidos pendientes se ofrecen.
PARTIDOS_OFRECIDOS = 5

SISTEMAS_VALIDOS = {"hattrick", "youth", "htointegrated"}


def _sistema(partido: m.Match) -> str:
    sistema = (partido.source_system or "hattrick").strip().lower()
    return sistema if sistema in SISTEMAS_VALIDOS else "hattrick"


async def _pendientes(session: AsyncSession, ht_team_id: int) -> list[m.Match]:
    """Los partidos a los que todavía se les puede mandar alineación.

    La hora manda sobre el estado guardado: un partido de anteayer puede
    seguir «sin terminar» si nadie sincronizó desde entonces.
    """
    ahora = datetime.now(UTC).replace(tzinfo=None)
    return list(
        (
            await session.execute(
                select(m.Match)
                .where(
                    (m.Match.home_team_ht_id == ht_team_id)
                    | (m.Match.away_team_ht_id == ht_team_id),
                    ~m.Match.status.ilike("finished"),
                    m.Match.played_at > ahora,
                    m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES),
                )
                .order_by(m.Match.played_at.asc())
                .limit(PARTIDOS_OFRECIDOS)
            )
        ).scalars()
    )


@router.get(
    "/teams/{team_id}/lineup/partidos-pendientes",
    summary="Partidos a los que se puede enviar alineación",
    dependencies=[Depends(require_team_owner)],
)
async def partidos_pendientes(
    team_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    partidos = await _pendientes(session, team.ht_team_id)
    nombres = await nombres_de_copa(session, team) if partidos else {}
    return {
        "matches": [
            {
                "htMatchId": p.ht_match_id,
                "playedAt": p.played_at.isoformat(),
                "isHome": p.home_team_ht_id == team.ht_team_id,
                "rival": p.away_team_name
                if p.home_team_ht_id == team.ht_team_id
                else p.home_team_name,
                "tournament": nombre_del_torneo(
                    p.match_type, p.cup_level, p.cup_level_index, nombres
                ),
                "ordersGiven": p.orders_given,
            }
            for p in partidos
        ],
        # Los nombres en español; la pantalla los pasa por el glosario oficial.
        "tactics": [{"code": c, "label": n} for c, n in TACTIC_TYPES.items()],
    }


class EnvioDeAlineacion(BaseModel):
    """Lo que la pantalla manda: el partido, los mismos mandos con los que se
    pidió el once que se está viendo, y las órdenes que eligió el usuario."""

    ht_match_id: int = Field(alias="htMatchId")
    formation: str | None = None
    central_defenders: int | None = Field(None, alias="centralDefenders")
    inner_midfielders: int | None = Field(None, alias="innerMidfielders")
    orders: str | None = None
    exclude: str | None = None
    tactica: int = 0
    capitan: int = 0
    tiro_libre: int = Field(0, alias="tiroLibre")
    penales: list[int] = Field(default_factory=list)
    #: Los once que la pantalla está enseñando. Si el servidor recalcula otros
    #: --hubo una sincronización en medio--, no se manda nada.
    titulares: list[int] = Field(default_factory=list)
    guardar: bool = False

    model_config = {"populate_by_name": True}


def _cambios_que_valen(
    cambios: list[dict[str, Any]], presentes: set[int]
) -> tuple[list[dict[str, Any]], int]:
    """Los cambios programados que siguen teniendo sentido, y cuántos se quitan.

    Un cambio nombra a quien sale y a quien entra. Si alguno de los dos ya no
    está en el once ni en el banquillo, Hattrick rechazaría el envío entero.
    """
    validos = [
        c
        for c in cambios
        if all(
            int(c.get(k) or 0) in presentes or not int(c.get(k) or 0)
            for k in ("playerin", "playerout")
        )
    ]
    return validos, len(cambios) - len(validos)


@router.post(
    "/teams/{team_id}/lineup/enviar",
    summary="Prevé o envía a Hattrick la alineación de la pantalla",
    dependencies=[Depends(require_team_owner), Depends(limite("enviar-alineacion", 20))],
)
async def enviar_alineacion(
    team_id: int,
    envio: EnvioDeAlineacion,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    from app.api.v1.endpoints.analysis.alineacion import _lineup_sin_cache

    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")
    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    partido = next(
        (
            p
            for p in await _pendientes(session, team.ht_team_id)
            if p.ht_match_id == envio.ht_match_id
        ),
        None,
    )
    if partido is None:
        raise HTTPException(409, "ese partido ya no admite alineación")
    if envio.tactica not in TACTIC_TYPES:
        raise HTTPException(422, f"táctica desconocida: {envio.tactica}")

    once = await _lineup_sin_cache(
        team_id,
        formation=envio.formation,
        central_defenders=envio.central_defenders,
        inner_midfielders=envio.inner_midfielders,
        orders=envio.orders,
        exclude=envio.exclude,
        session=session,
        entrenando=False,
    )
    filas = once.get("lineup") or []
    if len(filas) < 11:
        raise HTTPException(409, once.get("warning") or "no hay once que enviar")
    titulares = {int(f["htPlayerId"]) for f in filas}
    if envio.titulares and set(envio.titulares) != titulares:
        raise HTTPException(
            409, "el once cambió desde que abriste la pantalla: recárgala antes de enviar"
        )
    # Capitán, tiro libre y penales, sólo entre los once: Hattrick los quiere
    # en la cancha, y uno de fuera se descartaría sin avisar.
    for nombre, valor in (
        ("capitán", envio.capitan),
        ("lanzador de tiros libres", envio.tiro_libre),
    ):
        if valor and valor not in titulares:
            raise HTTPException(422, f"el {nombre} tiene que estar entre los once")
    if any(p not in titulares for p in envio.penales if p):
        raise HTTPException(422, "los lanzadores de penales tienen que estar entre los once")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    version = FILE_VERSIONS["matchorders"]
    sistema = _sistema(partido)
    try:

        async def leer() -> dict[str, Any]:
            try:
                return await client.fetch(
                    "matchorders",
                    version=version,
                    matchID=partido.ht_match_id,
                    teamId=team.ht_team_id,
                    sourceSystem=sistema,
                    actionType="view",
                )
            except (CHPPAuthError, CHPPUnavailableError):
                raise
            except Exception:  # noqa: BLE001, sin órdenes previas se manda sólo lo elegido
                return {}

        actuales = await leer()
        banquillo = once.get("bench") or []
        presentes = titulares | {int(b["htPlayerId"]) for b in banquillo}
        cambios, quitados = _cambios_que_valen(list(actuales.get("substitutions") or []), presentes)
        try:
            payload = alineacion_para_hattrick(
                filas,
                banquillo,
                actuales={**actuales, "substitutions": cambios},
                tactica=envio.tactica,
                capitan=envio.capitan or None,
                tiro_libre=envio.tiro_libre or None,
                penales=envio.penales or None,
            )
        except AlineacionInvalidaError as exc:
            raise HTTPException(422, str(exc)) from exc

        respuesta = await client.alineacion(
            partido.ht_match_id,
            team.ht_team_id,
            payload,
            guardar=envio.guardar,
            version=version,
            source_system=sistema,
        )
        despues = await leer() if envio.guardar else {}
    except CHPPAuthError as exc:
        token_row.status = "revoked"
        await session.commit()
        # 409 Y NO 401 (2026-11-19). Ante un 401 el navegador renueva la
        # sesión y REPITE la petición sola: con un envío, eso podría mandar la
        # alineación dos veces. Aquí nunca sale un 401.
        raise HTTPException(409, "Hattrick revocó el acceso: reconecta tu cuenta") from exc
    except CHPPDeniedError as exc:
        # Lo que Hattrick dice que tiene el acceso, en el mismo error: tras
        # reconectar, el usuario seguía viendo «falta el permiso» y no había
        # forma de saber si el acceso lo tenía (2026-11-19).
        tiene = await client.permisos()
        detalle = str(exc)
        if tiene is not None:
            lista = ", ".join(tiene) or "sólo lectura"
            detalle = f"{detalle}. Permisos que Hattrick dice que tiene tu acceso: {lista}"
        raise HTTPException(403, detalle) from exc
    except CHPPUnavailableError as exc:
        raise HTTPException(503, f"Hattrick no responde: {exc}") from exc
    finally:
        await client.aclose()

    prediccion = respuesta.get("prediction") if isinstance(respuesta, dict) else None
    ratings = (prediccion or {}).get("ratings") or {}
    enviados = sorted(r["id"] for r in payload["positions"] if r["id"])
    leidos = sorted(int(p["ht_player_id"]) for p in despues.get("positions") or [])
    habia = bool(actuales.get("available")) and bool(actuales.get("positions"))
    if envio.guardar and enviados == leidos:
        # Que Partidos, Rivales y el Dashboard lo sepan sin esperar al sync.
        partido.orders_given = True
        await session.commit()
    return {
        "guardar": envio.guardar,
        "htMatchId": partido.ht_match_id,
        "formation": once.get("formation"),
        "prediccion": (
            {nombre: int(ratings[nombre]) for nombre in SECTORES_PREVISTOS}
            if all(ratings.get(nombre) for nombre in SECTORES_PREVISTOS)
            else None
        ),
        # Lo que había antes, para avisar de que se sustituye.
        "habiaOrdenes": habia,
        "tacticaPrevia": actuales.get("tactic_type") if habia else None,
        "cambiosQuitados": quitados,
        # Tras guardar: lo que dijo Hattrick y si las órdenes releídas son las
        # que se mandaron.
        "guardada": bool(respuesta.get("orders_set")) if envio.guardar else False,
        "confirmada": envio.guardar and enviados == leidos,
        "motivo": respuesta.get("reason") or respuesta.get("chpp_error") or None,
    }
