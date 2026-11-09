"""El aviso de «programa un amistoso», con la ventana que pidió el usuario.

2026-11-01, dicho palabra por palabra: «desde 24 horas después de haber jugado
el último anterior amistoso hasta la misma hora en que tenga el país del
equipo programados los amistosos», y «siempre y cuando aún no esté
programado».
"""

import asyncio
from datetime import UTC, datetime, timedelta

from app.api.v1.endpoints.analysis.alertas import _lo_del_amistoso
from app.domain.engines.insights import Severity, amistoso_sin_programar
from app.domain.value_objects.ht_constants import (
    MATCH_TYPE_CUP,
    MATCH_TYPE_FRIENDLY,
    MATCH_TYPE_LEAGUE,
)
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

# El amistoso de la semana pasada: miércoles a las 21:40.
ULTIMO = datetime(2026, 10, 28, 21, 40, tzinfo=UTC)
RANURA = ULTIMO + timedelta(days=7)


def test_avisa_en_mitad_de_la_ventana() -> None:
    avisos = amistoso_sin_programar(
        ULTIMO,
        RANURA,
        ya_programado=False,
        ahora=ULTIMO + timedelta(days=3),
        en_copa=False,
    )
    assert len(avisos) == 1
    assert avisos[0].key == "match.friendly_unscheduled"
    assert avisos[0].severity is Severity.OPPORTUNITY
    # El detalle dice hasta cuándo da tiempo, que es lo accionable.
    assert "04/11" in avisos[0].detail


def test_calla_las_primeras_veinticuatro_horas() -> None:
    """Antes de eso el aviso llega pisando el partido que se acaba de jugar."""
    assert (
        amistoso_sin_programar(
            ULTIMO,
            RANURA,
            ya_programado=False,
            ahora=ULTIMO + timedelta(hours=23),
            en_copa=False,
        )
        == []
    )
    # Y en cuanto pasan las 24, habla.
    assert (
        amistoso_sin_programar(
            ULTIMO,
            RANURA,
            ya_programado=False,
            ahora=ULTIMO + timedelta(hours=24, minutes=1),
            en_copa=False,
        )
        != []
    )


def test_calla_pasada_la_hora_de_los_amistosos() -> None:
    """Después ya no da tiempo: avisar sería reprochar."""
    assert (
        amistoso_sin_programar(ULTIMO, RANURA, ya_programado=False, ahora=RANURA, en_copa=False)
        == []
    )


def test_calla_si_ya_hay_uno_concertado() -> None:
    assert (
        amistoso_sin_programar(
            ULTIMO,
            RANURA,
            ya_programado=True,
            ahora=ULTIMO + timedelta(days=3),
            en_copa=False,
        )
        == []
    )


def test_EN_COPA_no_se_avisa_aunque_toque() -> None:
    """2026-11-08, usuario: «el aviso de "no tienes amistoso" sólo aplica
    cuando no estás en Copa».

    Y no es una preferencia: el hueco de entre semana es UNO. Mientras sigas
    en la copa lo ocupa el partido de copa, así que pedir un amistoso es pedir
    algo donde no cabe nada. Mismo instante que la primera prueba de este
    fichero, que SÍ avisa: lo único que cambia es la copa.
    """
    assert (
        amistoso_sin_programar(
            ULTIMO,
            RANURA,
            ya_programado=False,
            ahora=ULTIMO + timedelta(days=3),
            en_copa=True,
        )
        == []
    )


def test_sin_ningun_amistoso_jugado_no_se_inventa_la_hora() -> None:
    assert (
        amistoso_sin_programar(None, None, ya_programado=False, ahora=ULTIMO, en_copa=False) == []
    )


# --------------------------------------------------------------------------
# La ranura, deducida de la base
# --------------------------------------------------------------------------


async def _con_amistosos(*partidos: tuple[int, datetime, bool]):
    """`(match_type, cuándo, jugado)` por cada partido."""
    factory, team_id = await seeded_session()
    async with factory() as s:
        for i, (tipo, cuando, jugado) in enumerate(partidos):
            s.add(
                m.Match(
                    ht_match_id=774_000_000 + i,
                    played_at=cuando,
                    match_type=tipo,
                    status="finished" if jugado else "UPCOMING",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=690_000 + i,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Cualquiera",
                    home_goals=3 if jugado else -1,
                    away_goals=1 if jugado else -1,
                )
            )
        await s.commit()
    return factory, team_id


def _avisos(factory, team_id, ahora):
    async def go():
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            return await _lo_del_amistoso(s, team, ahora)

    return asyncio.run(go())


def test_la_ranura_sale_del_ultimo_amistoso_jugado() -> None:
    factory, team_id = asyncio.run(_con_amistosos((MATCH_TYPE_FRIENDLY, ULTIMO, True)))
    avisos = _avisos(factory, team_id, ULTIMO + timedelta(days=2))
    assert len(avisos) == 1
    # Siete días después del último, misma hora: 4 de noviembre a las 21:40.
    assert "04/11" in avisos[0].detail
    assert "21:40" in avisos[0].detail


def test_un_amistoso_ya_programado_calla_el_aviso() -> None:
    factory, team_id = asyncio.run(
        _con_amistosos(
            (MATCH_TYPE_FRIENDLY, ULTIMO, True),
            (MATCH_TYPE_FRIENDLY, RANURA, False),
        )
    )
    assert _avisos(factory, team_id, ULTIMO + timedelta(days=2)) == []


def test_un_partido_de_liga_programado_no_cuenta_como_amistoso() -> None:
    factory, team_id = asyncio.run(
        _con_amistosos(
            (MATCH_TYPE_FRIENDLY, ULTIMO, True),
            (MATCH_TYPE_LEAGUE, ULTIMO + timedelta(days=4), False),
        )
    )
    assert len(_avisos(factory, team_id, ULTIMO + timedelta(days=2))) == 1


def test_si_el_ultimo_amistoso_es_de_hace_tres_semanas_la_ranura_es_la_proxima() -> None:
    """Sumar semanas enteras hasta pasar de ahora: el hueco es semanal, y el
    aviso tiene que hablar del de esta semana, no del de hace tres."""
    hace_tres = ULTIMO - timedelta(days=21)
    factory, team_id = asyncio.run(_con_amistosos((MATCH_TYPE_FRIENDLY, hace_tres, True)))
    avisos = _avisos(factory, team_id, ULTIMO + timedelta(days=2))
    assert len(avisos) == 1
    assert "04/11" in avisos[0].detail


# --------------------------------------------------------------------------
# Seguir en copa, visto desde la base
# --------------------------------------------------------------------------


def _con_bandera(factory, team_id: int, valor: bool | None) -> None:
    async def go() -> None:
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            team.still_in_cup = valor
            await s.commit()

    asyncio.run(go())


def test_la_bandera_de_copa_de_hattrick_calla_el_aviso() -> None:
    """`still_in_cup` sale de `teamdetails` y es la fuente autorizada: dice si
    el equipo sigue vivo en la copa AHORA, sin tener que deducirlo."""
    factory, team_id = asyncio.run(_con_amistosos((MATCH_TYPE_FRIENDLY, ULTIMO, True)))
    _con_bandera(factory, team_id, True)
    assert _avisos(factory, team_id, ULTIMO + timedelta(days=2)) == []

    # Eliminado y SIN copa programada: el hueco queda libre y el aviso vuelve.
    # Las dos condiciones hacen falta; con un cruce en el calendario seguiría
    # callado, aunque la bandera diga que no (ver la prueba del cambio de
    # temporada, más abajo).
    _con_bandera(factory, team_id, False)
    assert len(_avisos(factory, team_id, ULTIMO + timedelta(days=2))) == 1


def test_sin_bandera_manda_que_haya_copa_pendiente() -> None:
    """`still_in_cup=None` es «no lo sabemos»: el club se conectó antes de que
    se leyera. Entonces se mira si hay copa por jugar."""
    factory, team_id = asyncio.run(
        _con_amistosos(
            (MATCH_TYPE_FRIENDLY, ULTIMO, True),
            (MATCH_TYPE_CUP, ULTIMO + timedelta(days=4), False),
        )
    )
    _con_bandera(factory, team_id, None)
    assert _avisos(factory, team_id, ULTIMO + timedelta(days=2)) == []


def test_UNA_COPA_PROGRAMADA_GANA_A_LA_BANDERA_EN_FALSO() -> None:
    """El caso del cambio de temporada, dicho por el usuario el 2026-11-08:
    «pero ya estoy en la Copa de esta temporada».

    Entre quedar eliminado y que Hattrick sortee la copa siguiente hay una
    ventana en la que la bandera dice NO --y es cierta, para la copa que
    terminó-- mientras el primer cruce de la nueva ya está en el calendario.
    Si mandara la bandera, el aviso saldría justo cuando el hueco está
    ocupado. Un partido con fecha es mejor prueba que una bandera.
    """
    factory, team_id = asyncio.run(
        _con_amistosos(
            (MATCH_TYPE_FRIENDLY, ULTIMO, True),
            (MATCH_TYPE_CUP, ULTIMO + timedelta(days=4), False),
        )
    )
    _con_bandera(factory, team_id, False)
    assert _avisos(factory, team_id, ULTIMO + timedelta(days=2)) == []


def test_sin_bandera_y_sin_copa_pendiente_el_aviso_sale() -> None:
    """Mejor recordar de más que de menos: quien acaba de conectar el club no
    tiene copas sincronizadas todavía, y callarse le escondería el hueco."""
    factory, team_id = asyncio.run(_con_amistosos((MATCH_TYPE_FRIENDLY, ULTIMO, True)))
    _con_bandera(factory, team_id, None)
    assert len(_avisos(factory, team_id, ULTIMO + timedelta(days=2))) == 1


def test_una_copa_YA_JUGADA_no_cuenta_como_seguir_en_copa() -> None:
    """La de la semana pasada no ocupa el hueco de ésta."""
    factory, team_id = asyncio.run(
        _con_amistosos(
            (MATCH_TYPE_FRIENDLY, ULTIMO, True),
            (MATCH_TYPE_CUP, ULTIMO - timedelta(days=1), True),
        )
    )
    _con_bandera(factory, team_id, None)
    assert len(_avisos(factory, team_id, ULTIMO + timedelta(days=2))) == 1
