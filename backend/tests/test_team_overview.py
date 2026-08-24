"""Sección Equipo (MVP 2026-08-16): la plantilla promediada por grupos.

Lo que se fija aquí no son los números concretos de un fixture, sino las
reglas de diseño: tres grupos son series semanales con etiqueta TT-ss, y
varias métricas solo pueden compartir eje cuando comparten escala. TSI contra
salario no la comparte — un índice contra dinero —, así que van separados.
"""
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


class FakeCHPP:
    async def fetch(self, file: str, version: str = "latest", **_params: Any) -> dict[str, Any]:
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


@pytest.fixture
def seeded() -> tuple[TestClient, int]:
    import asyncio

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            team = m.Team(
                ht_team_id=537758, name="Pulgas Arrechas",
                currency_rate=10.0, currency_name="US$",
            )
            s.add(team)
            await s.commit()
            team_id = team.id
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        return team_id

    team_id = asyncio.run(setup())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, team_id
    app.dependency_overrides.clear()


def test_the_groups_are_served_with_the_squad_average(
    seeded: tuple[TestClient, int],
) -> None:
    client, team_id = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/overview")
    assert resp.status_code == 200
    body = resp.json()

    assert body["playerCount"] > 0
    assert [g["label"] for g in body["groups"]] == [
        "Habilidades", "Salario y TSI", "HTMS", "Mejor posición", "Clases de Jugador",
    ]
    skills = body["groups"][0]
    # Las 7 habilidades + Experiencia, Fidelidad, Resistencia y Forma.
    assert len(skills["metrics"]) == 11
    for metric in skills["metrics"]:
        assert 0 <= metric["value"] <= metric["scaleMax"]
    # La palabra de Hattrick solo tiene sentido en la escala 0-20.
    assert all(mtr["valueLabel"] for mtr in skills["metrics"][:9])


def test_best_position_stays_a_snapshot_and_the_rest_are_timelines(
    seeded: tuple[TestClient, int],
) -> None:
    """Mejor posición es el reparto de HOY, no una serie: cuántos jugadores
    tienen cada puesto como el suyo. Los otros tres sí evolucionan."""
    client, team_id = seeded
    groups = {g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]}

    assert groups["best_position"]["chart"] == "pitch"
    assert groups["best_position"]["weeks"] == []
    # Las siete habilidades comparten techo; Forma y Condición traen el suyo.
    por_clave = {mtr["key"]: mtr["scaleMax"] for mtr in groups["skills"]["metrics"]}
    assert {por_clave[col] for col in ("keeper", "defending", "scoring")} == {20.0}
    # Los grupos que no comparten eje tienen que explicar por qué.
    for key in ("market", "best_position"):
        assert groups[key]["note"], key


def test_best_position_is_a_head_count_not_an_average(
    seeded: tuple[TestClient, int],
) -> None:
    client, team_id = seeded
    body = client.get(f"/api/v1/teams/{team_id}/overview").json()
    best = next(g for g in body["groups"] if g["key"] == "best_position")

    assert all(mtr["display"] == "count" for mtr in best["metrics"])
    # Cada jugador aporta exactamente una mejor posición.
    assert sum(mtr["value"] for mtr in best["metrics"]) == body["playerCount"]


def test_the_weekly_series_are_labelled_tt_ss_and_share_one_timeline(
    seeded: tuple[TestClient, int],
) -> None:
    client, team_id = seeded
    body = client.get(f"/api/v1/teams/{team_id}/overview").json()
    groups = {g["key"]: g for g in body["groups"]}

    for key in ("skills", "market"):
        group = groups[key]
        assert group["chart"] == "line", key
        assert group["weeks"], key
        # Un valor por semana en cada serie: si no, la línea se desalinearía
        # del eje y cada punto quedaría en la semana equivocada.
        for chart in group["charts"]:
            for series in chart["series"]:
                assert len(series["values"]) == len(group["weeks"]), (key, series["key"])

    # Los dos grupos con serie comparten exactamente la misma línea de tiempo.
    assert groups["skills"]["weeks"] == groups["market"]["weeks"]


def test_tsi_and_salary_never_share_an_axis(
    seeded: tuple[TestClient, int],
) -> None:
    """Un índice y dinero no se comparan. Van en gráficas separadas."""
    client, team_id = seeded
    groups = {g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]}

    market = groups["market"]["charts"]
    assert [ch["key"] for ch in market] == ["salary", "tsi", "tsi_total", "cost_per_tsi"]
    # Sin techo fijo: cada una con su propio eje. Dos líneas por gráfica:
    # plantilla entera y los 11 de más TSI.
    assert [len(ch["series"]) for ch in market] == [2, 2, 2, 2]
    assert all(ch["scaleMax"] is None for ch in market)
    # El hueco entre las dos líneas se sombrea donde miden lo mismo sobre
    # poblaciones distintas. En el coste por punto no: ahí las líneas se
    # cruzan y el área entre ellas no sería ninguna cantidad.
    assert [ch["band"] for ch in market] == [True, True, True, False]


def test_total_tsi_of_the_top_eleven_never_exceeds_the_squad(
    seeded: tuple[TestClient, int],
) -> None:
    """La suma del once de más TSI es un subconjunto de la suma del plantel,
    así que la banda gris entre ambas es lo que aportan los demás — nunca
    puede salir negativa."""
    client, team_id = seeded
    groups = {g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]}
    total = next(ch for ch in groups["market"]["charts"] if ch["key"] == "tsi_total")

    plantilla, once = (s["values"] for s in total["series"])
    assert any(v is not None for v in plantilla)
    for todos, mejores in zip(plantilla, once):
        if todos is None or mejores is None:
            continue
        assert mejores <= todos


def test_a_week_without_loyalty_readings_is_never_a_zero(
    seeded: tuple[TestClient, int],
) -> None:
    """La Fidelidad no se persistía al principio y esos snapshots quedaron en
    0 — comprobado en la base: `loyalty` y `leadership` valen 0 en exactamente
    las mismas filas. Liderazgo empieza en 1 en Hattrick, así que un 0 suyo
    delata la lectura incompleta y esa semana nunca se cuenta como media de
    cero (el tramo inicial se estira aparte, sólo para dibujar)."""
    client, team_id = seeded
    groups = {g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]}

    fidelidad = [
        s for ch in groups["skills"]["charts"] for s in ch["series"]
        if s["label"] == "Fidelidad"
    ]
    assert fidelidad
    for series in fidelidad:
        for value in series["values"]:
            assert value is None or value > 0, series["label"]


def test_skills_splits_the_long_scale_from_the_short_one(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, pedido explícito: dos gráficas dentro de Habilidades.

    Arriba lo que se mide de 0 a 20 — las siete habilidades más Experiencia y
    Fidelidad. Abajo Resistencia y Forma, en un eje 1-9. Juntas, una Forma
    media de 5,6 se leería como baja en un eje que llega a 20."""
    client, team_id = seeded
    skills = {
        g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]
    }["skills"]

    # Tres desde el 2026-08-19: entre ambas entró la edad media, que tampoco
    # comparte eje con nada (son años, no niveles).
    assert len(skills["charts"]) == 3
    largo, edad, corto = skills["charts"]
    assert [s["label"] for s in edad["series"]] == ["Edad promedio"]

    assert [s["label"] for s in largo["series"]] == [
        "Portería", "Defensa", "Jugadas", "Lateral", "Pases", "Anotación",
        "Balón parado", "Experiencia", "Fidelidad",
    ]
    assert (largo["scaleMin"], largo["scaleMax"]) == (0.0, 20.0)

    assert [s["label"] for s in corto["series"]] == ["Resistencia", "Forma"]
    assert (corto["scaleMin"], corto["scaleMax"]) == (1.0, 9.0)


def test_the_leading_loyalty_gap_is_stretched_but_inner_gaps_are_not() -> None:
    """2026-08-16, pedido explícito y sólo estético: el tramo inicial vacío se
    estira con la primera lectura conocida para que la línea no arranque
    cortada. Un hueco INTERIOR sí significa "esa semana no se leyó" y taparlo
    escondería una laguna real."""
    from app.application.queries.weekly import backfill_leading_gaps

    assert backfill_leading_gaps([None, None, 8.1, 7.8]) == [8.1, 8.1, 8.1, 7.8]
    assert backfill_leading_gaps([8.1, None, 7.8]) == [8.1, None, 7.8]
    assert backfill_leading_gaps([None, None]) == [None, None]
    assert backfill_leading_gaps([]) == []


def test_cost_per_tsi_ignores_players_without_tsi_but_the_means_do_not(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, pedido explícito: los TSI 0 se ignoran SOLO en el cociente.

    Se calcula sumando antes de dividir sobre los jugadores CON índice —
    promediar el cociente jugador a jugador daría infinito con un TSI 0 y
    estaría dominado por los índices bajos. Las medias de salario y de TSI
    siguen contando a toda la plantilla, así que el ratio NO tiene por qué
    coincidir con dividir una por la otra."""
    client, team_id = seeded
    market = {
        g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]
    }["market"]
    por_clave = {ch["key"]: ch["series"][0]["values"] for ch in market["charts"]}

    for salario, tsi, ratio in zip(
        por_clave["salary"], por_clave["tsi"], por_clave["cost_per_tsi"], strict=True,
    ):
        if not tsi:
            continue
        assert ratio is not None and ratio > 0
        # Mismo orden de magnitud que el cociente de las medias, pero sin
        # obligación de ser idéntico: la población no es la misma.
        assert 0.5 < ratio / (salario / tsi) < 2.0

    assert "SOLO en el coste por punto" in market["note"]


def test_the_pitch_folds_the_nineteen_variants_into_six_lines(
    seeded: tuple[TestClient, int],
) -> None:
    """Las seis líneas están siempre presentes y el reparto suma la plantilla:
    cada jugador aporta su mejor puesto a UNA sola."""
    client, team_id = seeded
    body = client.get(f"/api/v1/teams/{team_id}/overview").json()
    best = next(g for g in body["groups"] if g["key"] == "best_position")

    assert [sl["key"] for sl in best["pitch"]] == [
        "keeper", "central_defender", "wingback",
        "inner_midfield", "winger", "forward",
    ]
    assert sum(sl["count"] for sl in best["pitch"]) == body["playerCount"]


def test_the_best_of_a_line_is_measured_over_the_whole_squad(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, pedido explícito: el resumen de cada línea sale de evaluar
    a TODA la plantilla en sus variantes (central normal, ofensivo, hacia
    lateral) y quedarse con la mejor.

    Son dos poblaciones distintas y no deben confundirse: `count` cuenta a
    quienes tienen esa línea como su mejor puesto, y puede ser 0 mientras el
    mejor rating existe igual — alguien de otro puesto puede cubrirla. Por eso
    el mejor rating de una línea nunca es menor que el mejor rating de los que
    la tienen como puesto natural.
    """
    client, team_id = seeded
    body = client.get(f"/api/v1/teams/{team_id}/overview").json()
    best = next(g for g in body["groups"] if g["key"] == "best_position")

    for slot in best["pitch"]:
        assert slot["bestRating"] is not None, slot["key"]
        assert slot["topPlayer"], slot["key"]
        # La variante concreta que dio ese máximo pertenece a la línea.
        assert slot["bestVariantLabel"], slot["key"]

    por_linea = {sl["key"]: sl["bestRating"] for sl in best["pitch"]}
    naturales: dict[str, float] = {}
    for player in client.get(f"/api/v1/teams/{team_id}/squad").json()["players"]:
        from app.application.queries.team_overview import pitch_line_of

        linea = pitch_line_of(player["bestPosition"]["position"])
        if linea is not None:
            naturales[linea] = max(
                naturales.get(linea, 0.0), player["bestPosition"]["rating"]
            )
    for linea, mejor_natural in naturales.items():
        assert por_linea[linea] >= mejor_natural - 1e-6, linea


def test_wingback_is_not_swallowed_by_winger() -> None:
    """`winger` y `wingback` comparten las cinco primeras letras: resolver por
    el primer prefijo que encaje mandaría a los laterales a la banda."""
    from app.application.queries.team_overview import pitch_line_of

    assert pitch_line_of("wingback_offensive") == "wingback"
    assert pitch_line_of("winger_defensive") == "winger"
    assert pitch_line_of("central_defender_towards_wing") == "central_defender"
    assert pitch_line_of("inventada") is None


def test_every_market_chart_carries_the_top_eleven_line(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, pedido explícito: las tres gráficas llevan además la línea
    del once de más TSI. Comparten eje con la plantilla entera porque son la
    misma medida sobre dos conjuntos — eso es lo que se quiere comparar.

    El once de más TSI tiene por fuerza un TSI medio mayor o igual que la
    plantilla entera: es un subconjunto elegido justo por eso.
    """
    client, team_id = seeded
    market = {
        g["key"]: g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]
    }["market"]

    for chart in market["charts"]:
        assert [sr["label"] for sr in chart["series"]] == [
            "Plantilla completa", "11 mejores TSI",
        ], chart["key"]
        completa, top = chart["series"]
        assert len(top["values"]) == len(completa["values"])

    tsi = next(ch for ch in market["charts"] if ch["key"] == "tsi")
    for completa, top in zip(tsi["series"][0]["values"], tsi["series"][1]["values"], strict=True):
        if completa is None or top is None:
            continue
        assert top >= completa


def test_rating_a_player_without_form_or_stamina_silently_yields_zero() -> None:
    """Trampa real encontrada al construir la cancha: `rate_all` no exige
    `form` ni `stamina`; si faltan devuelve 0.0 sin avisar y la línea entera
    aparece vacía. Este test la deja documentada para que nadie vuelva a
    armar un dict de jugador incompleto."""
    from app.domain.engines.position_engine import rate_all

    base = {
        "age_years": 25, "age_days": 0, "specialty": 0, "leadership": 3,
        "loyalty": 5, "experience": 5,
        "skills": {
            "keeper": 1, "defending": 5, "playmaking": 8, "winger": 6,
            "passing": 10, "scoring": 18, "set_pieces": 3,
        },
    }
    sin_forma = next(r for r in rate_all(base) if r.position == "forward")
    completo = next(
        r for r in rate_all({**base, "form": 6, "stamina": 7})
        if r.position == "forward"
    )
    assert sin_forma.rating == 0.0
    assert completo.rating > 0


def test_the_line_average_belongs_to_the_natural_population_only(
    seeded: tuple[TestClient, int],
) -> None:
    """La media es de quienes tienen esa línea como su MEJOR puesto, con el
    rating de ese puesto. No se mezcla con `bestRating`, que sale de evaluar a
    toda la plantilla: por eso la media puede ser mayor o menor que él sin que
    haya nada roto, salvo que el mejor de la línea nunca puede quedar por
    debajo de la media de los naturales."""
    client, team_id = seeded
    best = next(
        g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]
        if g["key"] == "best_position"
    )

    for slot in best["pitch"]:
        if slot["count"] == 0:
            assert slot["averageRating"] is None, slot["key"]
        else:
            assert slot["averageRating"] is not None, slot["key"]
            assert slot["bestRating"] >= slot["averageRating"] - 1e-6, slot["key"]


def test_captain_and_free_kick_taker_are_roles_not_pitch_positions(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, pedido explícito: van al lado de la cancha, no sobre ella.

    Se sirven aparte de `pitch` para que la interfaz no pueda dibujarlos como
    un puesto más. Su índice usa otra fórmula del motor y NO está en la escala
    0-20 de las posiciones — de hecho suele pasarse de 20 —, así que tampoco
    puede compartir la barra de las tarjetas del campo.
    """
    client, team_id = seeded
    best = next(
        g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]
        if g["key"] == "best_position"
    )

    assert [role["key"] for role in best["specialRoles"]] == [
        "captain", "set_piece_taker",
    ]
    # Ningún rol se cuela entre las líneas del campo.
    assert not {sl["key"] for sl in best["pitch"]} & {"captain", "set_piece_taker"}
    for role in best["specialRoles"]:
        assert role["topPlayer"]
        assert role["rating"] is not None


def test_a_goalkeeper_is_never_recommended_to_take_free_kicks(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, regla de juego dada por el usuario. El motor puntúa el
    balón parado sin mirar el puesto, así que un portero con buen tiro libre
    puede quedar primero — y recomendarlo es un disparate, no un hallazgo.

    El capitán sí puede ser portero: el veto es sólo para las faltas.
    """
    client, team_id = seeded
    body = client.get(f"/api/v1/teams/{team_id}/overview").json()
    best = next(g for g in body["groups"] if g["key"] == "best_position")
    roles = {r["key"]: r["topPlayer"] for r in best["specialRoles"]}

    porteros = {
        p["name"] for p in client.get(f"/api/v1/teams/{team_id}/squad").json()["players"]
        if p["bestPosition"]["position"] == "keeper"
    }
    assert porteros, "el fixture debe tener al menos un portero para que esto pruebe algo"
    assert roles["set_piece_taker"] not in porteros


def test_player_classes_is_only_a_tab_with_nothing_behind_it_yet(
    seeded: tuple[TestClient, int],
) -> None:
    """2026-08-16, pedido explícito: "por ahora solo el Toggle Segment".

    Viaja sin series, sin cancha y sin métricas para que la interfaz no pueda
    dibujar nada — el `chart="pending"` es lo que la hace decir "por definir"
    en vez de rellenar el hueco con una métrica inventada.
    """
    client, team_id = seeded
    classes = next(
        g for g in client.get(f"/api/v1/teams/{team_id}/overview").json()["groups"]
        if g["key"] == "player_classes"
    )

    assert classes["label"] == "Clases de Jugador"
    assert classes["chart"] == "pending"
    assert classes["charts"] == []
    assert classes["pitch"] == []
    assert classes["metrics"] == []
    assert classes["specialRoles"] == []


def test_la_suma_semanal_no_pierde_a_quien_no_cambio_esa_semana() -> None:
    """`player_snapshots` escribe fila solo cuando algo cambia.

    2026-08-24, caso real: la semana en curso tenia 7 fotos de 24 jugadores y
    "HTMS sumado de la plantilla" se desplomaba de 27.000 a 6.500 como si el
    equipo se hubiera caido a pedazos. Lo que faltaba eran diecisiete
    jugadores, no habilidad. Para una media el sesgo se disimula; para una
    SUMA es demoledor.
    """
    import asyncio
    from datetime import datetime

    from app.application.queries.team_overview import TeamOverviewQueryService

    async def corre() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        async with factory() as s:
            equipo = m.Team(ht_team_id=1, name="Pulgas", currency_rate=1.0)
            s.add(equipo)
            await s.flush()
            usuario = m.User(ht_user_id=1, login_name="yo")
            s.add(usuario)
            await s.flush()
            sync = m.Sync(user_id=usuario.id, team_id=equipo.id, kind="players",
                          status="completed", started_at=datetime(2026, 8, 10))
            s.add(sync)
            await s.flush()

            def foto(pid: int, cuando: datetime) -> m.PlayerSnapshot:
                return m.PlayerSnapshot(
                    sync_id=sync.id, player_id=pid, captured_at=cuando,
                    age_years=25, age_days=0, tsi=1000, form=5, stamina=7,
                    experience=5, salary=1000, leadership=4, loyalty=1,
                    keeper=1, defending=5, playmaking=5, winger=5,
                    passing=5, scoring=5, set_pieces=5,
                    content_hash=bytes([pid]) * 32,
                )

            # Dos jugadores. La primera semana se fotografian los dos; la
            # segunda solo uno cambia algo.
            for i in (1, 2):
                jugador = m.Player(
                    team_id=equipo.id, ht_player_id=100 + i,
                    first_name=f"J{i}", last_name="Prueba",
                )
                s.add(jugador)
                await s.flush()
                s.add(foto(jugador.id, datetime(2026, 8, 10, 12)))
                if i == 1:
                    s.add(foto(jugador.id, datetime(2026, 8, 17, 12)))
            await s.commit()
            team_id = equipo.id

        async with factory() as s:
            semanal = await TeamOverviewQueryService(s)._weekly_averages(team_id)

        total = semanal.by_field["htms_total"]
        assert len(total) == 2, "dos semanas"
        assert total[0] == total[1], (
            "el que no cambio sigue en la plantilla: la suma no puede caer a la mitad"
        )
        await engine.dispose()

    asyncio.run(corre())
