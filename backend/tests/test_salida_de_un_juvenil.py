"""Cuando un canterano deja la academia, ¿qué cuenta la pantalla de Cambios?

2026-10-04, reportado por el usuario: echó a un juvenil y no vio nada. Lo que
había era una línea de resumen que además arrastraba salidas de syncs
anteriores, y ninguna tarjeta. Y Hattrick no dice si el chico ascendió o si lo
descartaste: desaparece de la lista igual en los dos casos, y su identificador
de juvenil no es el de su ficha de senior.

Lo que se vigila aquí:
  · una salida de ESTE sync se cuenta, y una de uno anterior no;
  · si el chico aparece en la plantilla con tu club como club de origen, se
    dice que ascendió; si no, sólo que salió.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.sync_comparison import (
    _ascendio_al_primer_equipo,
    _youth_report,
)
from app.infrastructure.db import models as m

HOY = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
async def base():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(equipo)
        await s.commit()
        yield s, equipo.id
    await engine.dispose()


async def _juvenil(s, team_id: int, nombre: str, apellido: str, left_at: datetime | None):
    juvenil = m.YouthPlayer(
        ht_youth_player_id=abs(hash(apellido)) % 10_000_000,
        team_id=team_id,
        first_name=nombre,
        last_name=apellido,
        arrived_at=HOY - timedelta(days=90),
        left_at=left_at,
    )
    s.add(juvenil)
    await s.commit()
    return juvenil


@pytest.mark.asyncio
async def test_solo_se_cuenta_la_salida_de_este_sync(base) -> None:
    """La de la semana pasada ya se contó la semana pasada.

    El corte era «desde que arrancó el sync ANTERIOR», así que una salida que
    el informe anterior ya había cantado volvía a salir en el siguiente. Visto
    en vivo: el informe de un día traía a dos chicos, y uno se había ido seis
    días antes.
    """
    s, team_id = base
    await _juvenil(s, team_id, "Alirio", "Asprilla", HOY)
    await _juvenil(s, team_id, "Raúl", "Gil de Atienza", HOY - timedelta(days=6))

    _, resumen = await _youth_report(
        s,
        team_id,
        sync_id=1,
        desde=HOY - timedelta(days=7),
        desde_este_sync=HOY - timedelta(minutes=5),
    )
    assert [x["name"] for x in resumen["left"]] == ["Alirio Asprilla"]


@pytest.mark.asyncio
async def test_la_salida_tiene_su_propia_tarjeta(base) -> None:
    """Una línea de resumen entre cinco tarjetas no la ve nadie."""
    s, team_id = base
    await _juvenil(s, team_id, "Alirio", "Asprilla", HOY)

    filas, _ = await _youth_report(
        s, team_id, sync_id=1, desde=None, desde_este_sync=HOY - timedelta(minutes=5)
    )
    tarjeta = next(f for f in filas if f["name"] == "Alirio Asprilla")
    assert [c["key"] for c in tarjeta["changes"]] == ["departure"]


@pytest.mark.asyncio
async def test_sin_senior_que_coincida_no_se_dice_que_ascendio(base) -> None:
    """Lo único que se sabe es que se fue, y eso es lo que se dice."""
    s, team_id = base
    juvenil = await _juvenil(s, team_id, "Alirio", "Asprilla", HOY)
    assert await _ascendio_al_primer_equipo(s, team_id, juvenil) is False


@pytest.mark.asyncio
async def test_el_mismo_nombre_en_la_plantilla_y_el_mismo_dia_es_un_ascenso(
    base,
) -> None:
    """El otro lado del movimiento, que es lo único que Hattrick deja ver."""
    s, team_id = base
    juvenil = await _juvenil(s, team_id, "Alirio", "Asprilla", HOY)
    senior = m.Player(
        ht_player_id=999_111_222,
        team_id=team_id,
        first_name="Alirio",
        last_name="Asprilla",
        # Tu propio club como club de origen: eso es un canterano tuyo.
        mother_club_team_id=537758,
    )
    s.add(senior)
    await s.commit()
    s.add(
        m.PlayerStint(
            player_id=senior.id,
            ht_player_id=senior.ht_player_id,
            team_id=team_id,
            arrived_at=HOY + timedelta(hours=3),
        )
    )
    await s.commit()

    assert await _ascendio_al_primer_equipo(s, team_id, juvenil) is True

    filas, resumen = await _youth_report(
        s, team_id, sync_id=1, desde=None, desde_este_sync=HOY - timedelta(minutes=5)
    )
    assert resumen["left"][0]["promoted"] is True
    tarjeta = next(f for f in filas if f["name"] == "Alirio Asprilla")
    assert [c["key"] for c in tarjeta["changes"]] == ["promoted"]


@pytest.mark.asyncio
async def test_un_tocayo_de_otro_club_no_cuenta_como_ascenso(base) -> None:
    """El club de origen es la mitad de la prueba, no sólo el nombre."""
    s, team_id = base
    juvenil = await _juvenil(s, team_id, "Alirio", "Asprilla", HOY)
    comprado = m.Player(
        ht_player_id=999_333_444,
        team_id=team_id,
        first_name="Alirio",
        last_name="Asprilla",
        mother_club_team_id=111_222,  # la cantera de otro
    )
    s.add(comprado)
    await s.commit()
    s.add(
        m.PlayerStint(
            player_id=comprado.id,
            ht_player_id=comprado.ht_player_id,
            team_id=team_id,
            arrived_at=HOY + timedelta(hours=3),
        )
    )
    await s.commit()

    assert await _ascendio_al_primer_equipo(s, team_id, juvenil) is False
