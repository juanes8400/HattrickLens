"""El mensaje del ojeador se pide UNA vez por canterano (2026-09-14).

Pedido del usuario: el informe inicial --quién lo trajo, desde dónde y qué dijo
al llegar-- no cambia nunca, así que no se vuelve a preguntar. Los refrescos
siguen existiendo para `MayUnlock`, pero se piden sin `showScoutCall` y no
tocan lo que ya estaba guardado. Comprobado contra Hattrick: sin ese parámetro
`MayUnlock` sigue llegando.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.application.commands.sync_team import SyncResult, SyncTeamHandler
from app.infrastructure.db import models as m
from tests.test_sync_flow import _setup

JUVENIL = 424402061


class DobleDeHattrick:
    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self.revelado = False

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        assert file == "youthplayerdetails"
        self.pedidos.append(params)
        ficha: dict[str, Any] = {
            "ht_youth_player_id": JUVENIL,
            "may_unlock": {"passing": not self.revelado},
            "scout_id": None,
            "scout_name": "",
            "scouting_region_id": None,
            "scout_comments": [],
        }
        if params.get("showScoutCall") == "true":
            ficha |= {
                "scout_id": 10768192,
                "scout_name": "Mauricio Guerra",
                "scouting_region_id": 1717,
                "scout_comments": [{"text": "Te traigo a un pasador."}],
            }
        return ficha


def test_el_mensaje_del_ojeador_se_pide_una_vez_y_no_se_pisa() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        ahora = datetime.now(UTC)
        async with uow as u:
            juvenil = m.YouthPlayer(
                ht_youth_player_id=JUVENIL,
                team_id=team_id,
                first_name="Alirio",
                last_name="Asprilla",
            )
            u.session.add(juvenil)
            await u.session.flush()
            juvenil_id = juvenil.id
            u.session.add(
                m.YouthSnapshot(
                    sync_id=1,
                    youth_player_id=juvenil_id,
                    captured_at=ahora - timedelta(days=1),
                    age_years=16,
                    age_days=10,
                    content_hash=b"a" * 32,
                )
            )
            await u.commit()

        chpp = DobleDeHattrick()
        handler = SyncTeamHandler(uow, chpp)

        async def un_sync() -> None:
            async with uow as u:
                await handler._sync_informes_de_ojeador(
                    u, team_id, ahora, SyncResult(sync_id=1, status="completed")
                )
                await u.commit()

        await un_sync()
        assert chpp.pedidos == [{"youthPlayerId": JUVENIL, "showScoutCall": "true"}]

        # Una foto nueva (la edad en días cambia en cada sync) y una habilidad
        # que ya se reveló: se refresca, pero sin pedir el mensaje.
        chpp.pedidos.clear()
        chpp.revelado = True
        async with uow as u:
            u.session.add(
                m.YouthSnapshot(
                    sync_id=1,
                    youth_player_id=juvenil_id,
                    captured_at=ahora + timedelta(days=1),
                    age_years=16,
                    age_days=11,
                    content_hash=b"b" * 32,
                )
            )
            await u.commit()
        await un_sync()
        assert chpp.pedidos == [{"youthPlayerId": JUVENIL}]

        async with uow as u:
            informe = await u.session.scalar(
                select(m.YouthScoutReport).where(m.YouthScoutReport.youth_player_id == juvenil_id)
            )
        assert informe is not None
        # El mensaje sigue siendo el de la primera vez...
        assert informe.scout_name == "Mauricio Guerra"
        assert informe.scouting_region_id == 1717
        assert json.loads(informe.comments_json) == [{"text": "Te traigo a un pasador."}]
        # ...y lo que sí cambia está al día.
        assert json.loads(informe.may_unlock_json) == {"passing": False}

    asyncio.run(run())
