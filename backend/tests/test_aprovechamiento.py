"""A posteriori (2026-11-26): el aprovechamiento de cada entrenamiento con lo
que de verdad se jugó. Las reglas son del usuario; ver
`app.domain.engines.aprovechamiento`."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.application.queries.aprovechamiento import AprovechamientoQueryService
from app.application.queries.post_match_training import TRAINING_POSITION_SHARES
from app.domain.engines import aprovechamiento as ap
from app.domain.engines.insights import entrenamiento_a_posteriori
from app.domain.engines.training_engine import default_setup
from app.infrastructure.db import models as m

from .conftest import seeded_session


def test_el_peso_por_edad_sigue_la_regla_de_los_34() -> None:
    """17 años pesa 3,2; 28 pesa 1; a los 34 deja de contar (regla del
    usuario, 2026-11-25). Que a los 34 dé 0 justo es lo que comprueba que el
    746 está bien sacado de la tabla HTMS."""
    assert ap.peso_por_edad(17, 0) == pytest.approx(3.2, abs=0.01)
    assert ap.peso_por_edad(28, 0) == pytest.approx(1.0)
    assert ap.peso_por_edad(34, 0) == pytest.approx(0.0, abs=1e-9)
    assert ap.peso_por_edad(36, 50) == 0.0
    assert ap.peso_por_edad(20, 0) > ap.peso_por_edad(25, 0) > ap.peso_por_edad(30, 0)


#: Las casillas de cada entrenamiento en UN partido, contadas a mano sobre la
#: tabla de quién entrena qué: Defensa son 3 centrales + 2 laterales; Lateral,
#: 2 extremos + 2 laterales a medias; Pases (def. y centr.), 5 defensas + 5
#: medios. Escritas aquí, no derivadas: si cambia la tabla, esto avisa.
CASILLAS_A_MANO = {2: 11, 3: 5, 4: 3, 5: 3, 6: 11, 7: 8, 8: 4, 9: 1, 10: 10, 11: 11, 12: 5}


@pytest.mark.parametrize("tipo", sorted(CASILLAS_A_MANO))
def test_las_casillas_de_cada_entrenamiento(tipo: int) -> None:
    assert ap.casillas(TRAINING_POSITION_SHARES[tipo]) == CASILLAS_A_MANO[tipo]


def _ideal_en(skill: str, m_: float, edad: int = 17, nivel: int = 8) -> ap.Entrenado:
    setup = default_setup(skill)
    return ap.Entrenado(
        ht_player_id=edad * 100 + nivel,
        name=f"J{edad}-{nivel}",
        exposicion=m_,
        minutos_utiles=m_ * 90,
        ritmo=ap.ritmo(skill, {skill: nivel}, edad, 0, setup),
    )


def test_el_ideal_en_todas_las_casillas_es_el_100() -> None:
    setup = default_setup("keeper")
    g = ap.ideal("keeper", setup)
    dos = [_ideal_en("keeper", 1.0), _ideal_en("keeper", 1.0)]
    r = ap.aprovechamiento(9, dos, casillas_por_partido=1, g_ideal=g)
    assert r.aprovechado == pytest.approx(1.0)
    assert r.casillas_que_entrenan == 2
    # La altura del punto entre su T media da el aprovechado: la gráfica
    # log-log pone cada entrenamiento en su diagonal por esto.
    assert r.semanas_por_nivel is not None
    assert r.aporte_por_casilla / r.semanas_por_nivel == pytest.approx(r.aprovechado)


def test_el_mismo_jugador_en_los_dos_partidos_llena_una_sola_casilla() -> None:
    """El caso de Ebbesen: 182′ en portería, pero el cupo es de 90′ por
    semana. Llena una casilla de dos y la mitad se desperdicia."""
    setup = default_setup("keeper")
    g = ap.ideal("keeper", setup)
    solo = ap.Entrenado(
        ht_player_id=1,
        name="Ebbesen",
        exposicion=1.0,
        minutos_utiles=182,
        ritmo=ap.ritmo("keeper", {"keeper": 8}, 17, 0, setup),
    )
    r = ap.aprovechamiento(9, [solo], casillas_por_partido=1, g_ideal=g)
    assert r.aprovechado == pytest.approx(0.5)
    assert r.minutos_sin_entrenar == pytest.approx(92)


def test_quien_mejor_lo_aprovecha_necesita_45_minutos() -> None:
    """Sin el mínimo ganaba un juvenil que jugó 2′ (Homeag, 22-nov)."""
    setup = default_setup("passing")
    g = ap.ideal("passing", setup)
    veterano = ap.Entrenado(
        1, "Veterano", 1.0, 90, ap.ritmo("passing", {"passing": 12}, 30, 0, setup)
    )
    juvenil = ap.Entrenado(2, "Juvenil", 0.02, 2, ap.ritmo("passing", {"passing": 4}, 20, 0, setup))
    r = ap.aprovechamiento(10, [veterano, juvenil], casillas_por_partido=10, g_ideal=g)
    assert r.mejor is not None and r.mejor.name == "Veterano"
    assert r.jugadores == 2


def test_un_nivel_divino_no_entrena() -> None:
    r = ap.ritmo("defending", {"defending": 20}, 25, 0, default_setup("defending"))
    assert r.por_semana == 0.0


def test_la_alerta_salta_con_cualquier_mejora_y_solo_a_tiempo() -> None:
    base: dict[str, object] = {
        "semana": "2026-11-27",
        "partidos": 2,
        "aun_se_puede_cambiar": True,
        "actual": "Pases (defensas y centrocampistas)",
        "actual_pct": 0.080,
        "mejor": "Defensa",
        "mejor_pct": 0.119,
    }
    [alerta] = entrenamiento_a_posteriori(**base)  # type: ignore[arg-type]
    assert alerta.key == "training.a_posteriori.2026-11-27"
    assert "Defensa" in alerta.title and "8.0%" in alerta.detail and "11.9%" in alerta.detail
    # Cualquier mejora, por pequeña que sea (elección del usuario).
    assert entrenamiento_a_posteriori(**{**base, "mejor_pct": 0.0801})  # type: ignore[arg-type]
    # Con un solo partido la semana no está completa.
    assert entrenamiento_a_posteriori(**{**base, "partidos": 1}) == []  # type: ignore[arg-type]
    # Pasado el corte ya se aplicó: avisar sería reprochar.
    assert entrenamiento_a_posteriori(**{**base, "aun_se_puede_cambiar": False}) == []  # type: ignore[arg-type]
    # Si el actual ya es el mejor, no hay nada que decir.
    assert entrenamiento_a_posteriori(**{**base, "mejor": base["actual"]}) == []  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_la_semana_de_liga_y_copa_de_punta_a_punta() -> None:
    """Un delantero que juega la liga y la copa: los dos partidos entran en
    la semana, Anotación lo entrena entero y Portería nada."""
    factory, team_id = await seeded_session()
    ahora = datetime.now(UTC)
    async with factory() as s:
        jugador = (
            await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .limit(1)
            )
        ).scalar_one()
        equipo = await s.get(m.Team, team_id)
        assert equipo is not None
        mundo = (await s.execute(select(m.WorldContext).limit(1))).scalar_one()
        mundo.training_date = ahora + timedelta(hours=6)
        mundo.refreshed_at = ahora
        for i, (tipo, hace) in enumerate(((1, 4), (3, 1))):
            s.add(
                m.Match(
                    ht_match_id=910000 + i,
                    played_at=ahora - timedelta(days=hace),
                    match_type=tipo,
                    status="Finished",
                    home_team_ht_id=equipo.ht_team_id,
                    away_team_ht_id=123,
                    home_team_name=equipo.name,
                    away_team_name=f"Rival {i}",
                    home_goals=1,
                    away_goals=0,
                )
            )
            s.add(
                m.PlayerMatchRating(
                    player_id=jugador.id,
                    ht_match_id=910000 + i,
                    position_code=112,
                    played_minutes=90,
                    rating=6.0,
                    captured_at=ahora - timedelta(days=hace),
                )
            )
        await s.commit()

    async with factory() as s:
        datos = await AprovechamientoQueryService(s).get(team_id)
    assert datos is not None
    assert datos["aunSePuedeCambiar"] is True
    assert [p["matchType"] for p in datos["partidos"]] == [1, 3]
    opciones = {o["trainingType"]: o for o in datos["opciones"]}
    anotacion, porteria = opciones[4], opciones[9]
    assert anotacion["casillas"] == 6  # 3 delanteros × 2 partidos
    assert anotacion["casillasQueEntrenan"] == pytest.approx(1.0)
    assert anotacion["minutosSinEntrenar"] == pytest.approx(90)
    assert anotacion["aprovechado"] > 0
    assert porteria["aprovechado"] == 0
    # Ordenadas de mejor a peor, y el mejor es el primero.
    valores = [o["aprovechado"] for o in datos["opciones"]]
    assert valores == sorted(valores, reverse=True)
    assert datos["mejor"] == datos["opciones"][0]["trainingType"]
    # Ni General ni Resistencia: Hattrick ya no deja ponerlos.
    assert not {0, 1} & set(opciones)
