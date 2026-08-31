"""Recontar exclusivamente Partidos con nosotros por etapa cerrada.

Herramienta de mantenimiento para el desarrollador. Usa el token CHPP activo
ya cifrado en la base; nunca imprime credenciales. El backfill normal de la
aplicacion ejecuta la misma logica por lotes, pero tambien atiende fichas y
reventas. Este script permite reparar solo el censo historico.

Uso:
    python scripts/backfill_games_by_stint.py --team-id 1
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main(team_id: int, limit: int | None, refresh_missing_age: bool) -> None:
    from app.application.commands.sync_team import SyncTeamHandler
    from app.core.config import settings
    from app.infrastructure.chpp.client import CHPPClient
    from app.infrastructure.db import models as m
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
    from app.infrastructure.security.tokens import decrypt_token

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        team = await session.get(m.Team, team_id)
        if team is None:
            raise SystemExit(f"No existe el equipo interno {team_id}")
        if team.owner_user_id is None:
            raise SystemExit("El equipo no tiene un usuario propietario")
        token = await session.scalar(
            select(m.CHPPToken).where(
                m.CHPPToken.user_id == team.owner_user_id,
                m.CHPPToken.status == "active",
            )
        )
        if token is None:
            raise SystemExit("No hay un token CHPP activo para este equipo")
        identities = {
            ht_player_id: (first_name, last_name)
            for ht_player_id, first_name, last_name in (
                await session.execute(
                    select(
                        m.Player.ht_player_id,
                        m.Player.first_name,
                        m.Player.last_name,
                    ).where(m.Player.team_id == team_id)
                )
            ).all()
        }

    client = CHPPClient(
        decrypt_token(token.oauth_token_enc),
        decrypt_token(token.oauth_secret_enc),
    )
    try:
        if refresh_missing_age:
            async with factory() as session:
                missing_age_ids = list(
                    (
                        await session.execute(
                            select(m.Player.ht_player_id)
                            .where(
                                m.Player.team_id == team_id,
                                ~m.Player.ht_player_id_is_transfer,
                                m.Player.age_years_at_sale.is_(None),
                                select(m.PlayerStint.id)
                                .where(
                                    m.PlayerStint.player_id == m.Player.id,
                                    m.PlayerStint.left_at.is_not(None),
                                    m.PlayerStint.arrived_at.is_(None),
                                    m.PlayerStint.from_academy.is_(True),
                                    m.PlayerStint.games_played_for_us.is_(None),
                                )
                                .exists(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            print(
                f"Intentando recuperar edad para {len(missing_age_ids)} "
                "canterano(s) historicos.",
                flush=True,
            )
            for index, ht_player_id in enumerate(missing_age_ids, start=1):
                identity = identities.get(ht_player_id)
                name = (
                    " ".join(part for part in identity if part).strip()
                    if identity is not None
                    else str(ht_player_id)
                )
                print(f"  edad [{index}/{len(missing_age_ids)}] {name}", flush=True)
                age_uow = SqlAlchemyUnitOfWork(factory)
                age_handler = SyncTeamHandler(age_uow, client)
                try:
                    async with age_uow:
                        await age_handler._apply_player_enrichment(
                            age_uow,
                            ht_player_id,
                            datetime.now(UTC).replace(tzinfo=None),
                        )
                        await age_uow.commit()
                except Exception as exc:  # noqa: BLE001 - mejor esfuerzo explicito
                    print(
                        f"    edad pendiente: {type(exc).__name__}: {exc}",
                        flush=True,
                    )

        probe_uow = SqlAlchemyUnitOfWork(factory)
        probe = SyncTeamHandler(probe_uow, client)
        async with probe_uow:
            pending = await probe.pendientes_de_ficha(probe_uow, team_id)
        player_ids = pending["censo"][:limit] if limit is not None else pending["censo"]
        print(f"Etapas por censar, agrupadas en {len(player_ids)} jugador(es).")

        completed = 0
        failed = 0
        for index, ht_player_id in enumerate(player_ids, start=1):
            identity = identities.get(ht_player_id)
            if identity is None:
                name = str(ht_player_id)
            else:
                name = " ".join(part for part in identity if part).strip() or str(ht_player_id)
            print(f"[{index}/{len(player_ids)}] {name}", flush=True)

            uow = SqlAlchemyUnitOfWork(factory)
            handler = SyncTeamHandler(uow, client)
            try:
                async with uow:
                    wrote = await handler._censar_partidos_del_stint(
                        uow, team_id, ht_player_id
                    )
                    await uow.commit()
                completed += int(wrote)
            except Exception as exc:  # noqa: BLE001 - cada jugador es reintentable
                failed += 1
                print(f"  pendiente por error: {type(exc).__name__}: {exc}", flush=True)

        final_uow = SqlAlchemyUnitOfWork(factory)
        final = SyncTeamHandler(final_uow, client)
        async with final_uow:
            remaining = await final.pendientes_de_ficha(final_uow, team_id)
        print(
            f"Completados: {completed}. Fallidos: {failed}. "
            f"Jugadores censables pendientes: {len(remaining['censo'])}."
        )
    finally:
        await client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--refresh-missing-age",
        action="store_true",
        help="Reintenta playerdetails para canteranos sin fecha inicial",
    )
    args = parser.parse_args()
    asyncio.run(main(args.team_id, args.limit, args.refresh_missing_age))
