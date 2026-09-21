"""Guardar los últimos partidos de tus rivales, para no repedirlos.

2026-09-09, pedido del usuario: «me dice que ya llamé muchísimas veces la info
de rivales y sus partidos, y es verdad. En Sync, vas a cargar los 5 partidos
oficiales de cada contrincante de Liga de una, guárdalos para que no toque
volverlos a llamar, y guardas el último eliminando el más antiguo».

2026-09-10, ampliado a petición del mismo usuario: también se guarda lo que la
ficha de rival pide EN VIVO --un rival de amistoso, uno traído con su
identificador, o un partido de liga jugado después del último sync--, «a
partir del primer llamado y que no se descarguen siempre de nuevo».

QUÉ SE AHORRA. Abrir la ficha de un rival costaba, por cada partido mirado,
una llamada de alineación y otra de detalle. Cinco partidos son diez llamadas,
y se pagaban ENTERAS cada vez que se abría la ficha, aunque fuera el mismo
rival diez minutos después. Un partido terminado no cambia nunca.

DOS ESCRITORES, UNA TABLA. El sync precarga a los contrincantes de liga y al
de copa; la ficha guarda lo que acaba de pedir. Los dos escriben con la misma
función y el mismo recorte, así que da igual quién llegue primero.

VENTANA DE CINCO POR CLASE. Cinco oficiales y cinco amistosos por rival, cada
clase con su propio recorte. Con un solo recorte de cinco, guardar los
amistosos de un rival echaba a sus oficiales, y la siguiente visita a los
oficiales los volvía a descargar: justo lo que se quería quitar.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as insert_postgres
from sqlalchemy.dialects.sqlite import insert as insert_sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.prediccion import TIPOS_DE_AMISTOSOS, TIPOS_OFICIALES
from app.domain.value_objects.ht_time import ht_to_utc
from app.infrastructure.db import models as m

_log = logging.getLogger(__name__)

#: Cuántos se guardan por rival Y POR CLASE. Es el mismo número que mira la
#: ficha (`MAX_MATCHES_ANALYSED`), y tiene que serlo: guardar menos dejaría a
#: la ficha pidiendo la diferencia en vivo.
PARTIDOS_GUARDADOS_POR_RIVAL = 5

#: La versión del lector de alineaciones que trae el CÓDIGO de posición de la
#: formación de arranque, que es lo que usa el marcaje al hombre. La ficha de
#: rival la importa de aquí en vez de tener la suya: si las dos discreparan,
#: lo guardado no serviría para lo que lo lee, y el desajuste sería silencioso
#: --posiciones que se leen como otra cosa, no un error--.
#:
#: NO confundir con la 2.1 que pide «Mejor alineación», que usa `RoleID`: en
#: esta versión ese campo es sólo un índice secuencial sin significado.
VERSION_ALINEACION = "1.2"


@dataclass
class ResumenDeRivales:
    """Qué hizo la precarga, para poder contarlo en el informe del sync."""

    rivales: int = 0
    partidos_nuevos: int = 0
    partidos_ya_estaban: int = 0
    borrados_por_antiguos: int = 0
    errores: list[str] = field(default_factory=list)


async def partidos_guardados(
    session: AsyncSession,
    team_ht_id: int,
    limite: int | None = PARTIDOS_GUARDADOS_POR_RIVAL,
) -> list[m.RivalMatch]:
    """Lo que hay guardado de un rival, del más viejo al más reciente.

    El orden importa y no es decorativo: quien resuma por «el último partido»
    necesita que el último de la lista sea el último de verdad.

    `limite=None` los trae todos, que es lo que necesita la ficha: con cinco
    por clase puede haber diez, y cortar a cinco dejaría fuera justo la clase
    que se va a mirar.
    """
    consulta = (
        select(m.RivalMatch)
        .where(m.RivalMatch.team_ht_id == team_ht_id)
        .order_by(m.RivalMatch.played_at.desc())
    )
    if limite is not None:
        consulta = consulta.limit(limite)
    filas = (await session.execute(consulta)).scalars()
    return list(reversed(list(filas)))


def alineacion_de(fila: m.RivalMatch) -> list[dict[str, Any]]:
    """La alineación guardada, o una lista vacía si el JSON llegó roto.

    Vacía y no una excepción: una alineación ilegible es un partido del que no
    se sabe quién jugó, no un motivo para no enseñar la ficha.
    """
    try:
        datos = json.loads(fila.lineup_json)
    except (TypeError, ValueError):
        return []
    return datos if isinstance(datos, list) else []


def ratings_de(fila: m.RivalMatch) -> dict[str, int] | None:
    """Los nueve del rival, o nada si a la fila le falta alguno.

    Entera o no cuenta, la misma regla que en la ficha: media lectura no es
    una lectura con ceros.
    """
    valores = {
        "midfield": fila.midfield,
        "left_def": fila.left_def,
        "central_def": fila.central_def,
        "right_def": fila.right_def,
        "left_att": fila.left_att,
        "central_att": fila.central_att,
        "right_att": fila.right_att,
        "sp_def": fila.set_pieces_def,
        "sp_att": fila.set_pieces_att,
    }
    if any(v is None for v in valores.values()):
        return None
    return {k: int(v) for k, v in valores.items() if v is not None}


def _valores_de_fila(
    team_ht_id: int,
    partido: dict[str, Any],
    lado: dict[str, Any],
    alineacion: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Una fila de `rival_matches`, desde lo que devuelven los lectores.

    `partido` es la cabecera del calendario o del archivo --los dos traen
    nombres y goles--; `lado` es el bloque DEL RIVAL en el detalle del partido.
    Devuelve `None` si la fecha no se puede leer: sin fecha no hay ventana en
    la que colocarlo.
    """
    cuando = ht_to_utc(partido.get("match_date", ""))
    if cuando is None:
        return None
    ratings = lado.get("ratings") or {}
    return {
        "team_ht_id": team_ht_id,
        "ht_match_id": partido["ht_match_id"],
        "match_type": partido["match_type"],
        "played_at": cuando,
        "home_team_ht_id": partido.get("home_team_id") or 0,
        "away_team_ht_id": partido.get("away_team_id") or 0,
        "home_team_name": (partido.get("home_team_name") or "")[:128],
        "away_team_name": (partido.get("away_team_name") or "")[:128],
        "home_goals": partido.get("home_goals", -1),
        "away_goals": partido.get("away_goals", -1),
        "midfield": ratings.get("midfield"),
        "left_def": ratings.get("left_def"),
        "central_def": ratings.get("central_def"),
        "right_def": ratings.get("right_def"),
        "left_att": ratings.get("left_att"),
        "central_att": ratings.get("central_att"),
        "right_att": ratings.get("right_att"),
        "set_pieces_def": ratings.get("set_pieces_def"),
        "set_pieces_att": ratings.get("set_pieces_att"),
        "tactic_type": lado.get("tactic_type") or 0,
        "tactic_skill": lado.get("tactic_skill") or 0,
        "formation": (lado.get("formation") or "")[:16] or None,
        "lineup_json": json.dumps(alineacion, ensure_ascii=False),
        "captured_at": datetime.now(UTC),
    }


async def _insertar_sin_duplicar(session: AsyncSession, filas: list[dict[str, Any]]) -> None:
    """Inserta, y si la fila ya estaba no hace nada.

    Hace falta desde que escriben dos: la ficha puede abrirse dos veces a la
    vez --dos pestañas, o un clic en el selector mientras carga-- y las dos
    peticiones intentarían guardar el mismo partido. Con un INSERT a secas la
    segunda reventaría contra la clave única y la ficha saldría con error por
    algo que ya estaba hecho.

    Se elige el dialecto porque la cláusula no es SQL estándar: SQLite en
    local, Postgres en producción.
    """
    if not filas:
        return
    dialecto = session.get_bind().dialect.name
    insert = insert_postgres if dialecto == "postgresql" else insert_sqlite
    await session.execute(
        insert(m.RivalMatch)
        .values(filas)
        .on_conflict_do_nothing(index_elements=["team_ht_id", "ht_match_id"])
    )


async def _recortar_a_la_ventana(session: AsyncSession, team_ht_id: int) -> int:
    """Deja los cinco más recientes de CADA clase, y borra el resto.

    Por clase y no en total: ver el porqué en la cabecera del módulo.

    Se resuelve con dos consultas por clase y no con un `DELETE ... LIMIT`
    porque SQLite no admite el segundo sin compilarlo con una opción que nadie
    garantiza.
    """
    borrados = 0
    es_amistoso = m.RivalMatch.match_type.in_(TIPOS_DE_AMISTOSOS)
    for clase in (es_amistoso, ~es_amistoso):
        sobran = list(
            (
                await session.execute(
                    select(m.RivalMatch.id)
                    .where(m.RivalMatch.team_ht_id == team_ht_id, clase)
                    .order_by(m.RivalMatch.played_at.desc())
                    .offset(PARTIDOS_GUARDADOS_POR_RIVAL)
                )
            ).scalars()
        )
        if sobran:
            await session.execute(delete(m.RivalMatch).where(m.RivalMatch.id.in_(sobran)))
            borrados += len(sobran)
    return borrados


async def guardar_lo_visto(
    session: AsyncSession,
    team_ht_id: int,
    partidos: list[dict[str, Any]],
    alineaciones: dict[int, list[dict[str, Any]]],
    lados: dict[int, dict[str, Any]],
) -> int:
    """Guarda lo que la ficha de rival acaba de pedir en vivo.

    Sólo entra un partido del que se pidieron las DOS cosas, alineación y
    detalle: guardar media fila obligaría a volver a pedir la otra mitad en la
    siguiente visita, y no ahorraría nada.

    No hace commit: eso lo decide quien llama, que es quien sabe si hay algo
    más en la misma transacción. Devuelve cuántas filas intentó guardar.
    """
    filas = []
    for partido in partidos:
        ht_match_id = partido["ht_match_id"]
        if ht_match_id not in alineaciones or ht_match_id not in lados:
            continue
        valores = _valores_de_fila(
            team_ht_id, partido, lados[ht_match_id], alineaciones[ht_match_id]
        )
        if valores is not None:
            filas.append(valores)
    if not filas:
        return 0
    await _insertar_sin_duplicar(session, filas)
    await _recortar_a_la_ventana(session, team_ht_id)
    return len(filas)


async def guardar_partidos_de_un_rival(
    session: AsyncSession,
    client: Any,
    team_ht_id: int,
    version_matches: str,
    version_matchdetails: str,
    resumen: ResumenDeRivales,
) -> None:
    """Deja en la base los últimos oficiales de UN rival, sin repetir llamadas."""
    try:
        calendario = (await client.fetch("matches", version=version_matches, teamID=team_ht_id))[
            "matches"
        ]
    except Exception as exc:  # noqa: BLE001, un rival caído no tumba el sync
        # Por el nombre legible, como todos los demás avisos (2026-09-20).
        # Éste vivía en otro fichero y la prueba que recorre el sync no
        # llegaba hasta aquí, así que se quedó diciendo «matches:».
        from app.application.commands.sync_team import _nombre_legible

        resumen.errores.append(f"{_nombre_legible('matches')} ({team_ht_id}): {exc}")
        return

    jugados = [
        mt
        for mt in calendario
        if mt.get("status", "").upper() == "FINISHED" and mt.get("match_type") in TIPOS_OFICIALES
    ]
    jugados.sort(key=lambda mt: mt.get("match_date", ""))
    ultimos = jugados[-PARTIDOS_GUARDADOS_POR_RIVAL:]
    if not ultimos:
        return

    ya = {
        fila.ht_match_id
        for fila in (
            await session.execute(select(m.RivalMatch).where(m.RivalMatch.team_ht_id == team_ht_id))
        ).scalars()
    }

    filas: list[dict[str, Any]] = []
    for mt in ultimos:
        ht_match_id = mt["ht_match_id"]
        if ht_match_id in ya:
            resumen.partidos_ya_estaban += 1
            continue
        # La fecha se mira ANTES de pedir nada: un partido sin fecha legible
        # no cabe en la ventana, y pedir su detalle sería gastar dos llamadas
        # para descartarlo.
        if ht_to_utc(mt.get("match_date", "")) is None:
            continue
        try:
            detalle = await client.fetch(
                "matchdetails", version=version_matchdetails, matchID=ht_match_id
            )
            alineacion = (
                await client.fetch(
                    "matchlineup",
                    version=VERSION_ALINEACION,
                    matchID=ht_match_id,
                    matchType=mt["match_type"],
                    teamID=team_ht_id,
                )
            )["players"]
        except Exception as exc:  # noqa: BLE001, un partido caído no tumba el sync
            resumen.errores.append(f"partido {ht_match_id} de {team_ht_id}: {exc}")
            continue

        # De qué lado del partido está este rival. Se busca por team_id y no
        # por posición: el mismo partido puede guardarse dos veces, una por
        # cada equipo, cuando los dos son contrincantes de liga.
        lado: dict[str, Any] = {}
        for cual in ("home", "away"):
            bloque = detalle.get(cual) or {}
            if bloque.get("team_id") == team_ht_id:
                lado = bloque
                break

        valores = _valores_de_fila(team_ht_id, mt, lado, alineacion)
        if valores is not None:
            filas.append(valores)
            resumen.partidos_nuevos += 1

    await _insertar_sin_duplicar(session, filas)
    await session.flush()
    resumen.borrados_por_antiguos += await _recortar_a_la_ventana(session, team_ht_id)


async def guardar_partidos_de_rivales(
    session: AsyncSession,
    client: Any,
    rivales: set[int],
    version_matches: str,
    version_matchdetails: str,
) -> ResumenDeRivales:
    """Lo mismo para todos los contrincantes conocidos, de una."""
    resumen = ResumenDeRivales(rivales=len(rivales))
    for team_ht_id in sorted(rivales):
        await guardar_partidos_de_un_rival(
            session,
            client,
            team_ht_id,
            version_matches,
            version_matchdetails,
            resumen,
        )
    if resumen.errores:
        _log.info("precarga de rivales con %d incidencias", len(resumen.errores))
    return resumen
