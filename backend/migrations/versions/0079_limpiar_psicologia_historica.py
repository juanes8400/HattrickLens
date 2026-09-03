"""Elimina los -1 historicos de Espiritu y Confianza.

El -1 de training.xml significa "temporalmente no disponible", no un nivel.
Esta revision limpia las dos huellas que dejo el comportamiento antiguo:

* En ``training_snapshots`` reemplaza cada -1 por el ultimo nivel valido del
  mismo equipo y campo; si aun no existia uno, lo deja como NULL.
* En ``sync_changes`` elimina los avisos falsos ``-1 -> nivel`` y reconstruye
  solamente los cambios psicologicos reales entre snapshots consecutivos.

Cuando cambia un snapshot tambien se recalcula su ``content_hash`` con el
payload canonico de training.xml. Asi la foto y su huella siguen contando la
misma historia y el siguiente sync no crea un duplicado.

La limpieza de datos es intencionalmente irreversible: el downgrade restaura
solo la revision de Alembic, no vuelve a inventar placeholders ni avisos
falsos. Este es el mismo criterio que usan otras limpiezas historicas del
proyecto.

Revision ID: 0079
Revises: 0078
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


TEAM_SPIRIT = {
    0: "Como en la Guerra Fría",
    1: "Muy agresivos",
    2: "Tensos",
    3: "Susceptibles",
    4: "Serenos",
    5: "Calmados",
    6: "Contentos",
    7: "Encantados",
    8: "Eufóricos",
    9: "Por las nubes",
    10: "Paraíso en la Tierra",
}

CONFIDENCE = {
    0: "Inexistente",
    1: "Por los suelos",
    2: "Muy baja",
    3: "Baja",
    4: "Decente",
    5: "Sólida",
    6: "Alta",
    7: "Muy alta",
    8: "Exagerada",
    9: "Desmedida",
}

PSYCHOLOGY = {
    "morale": ("Espíritu del equipo", TEAM_SPIRIT),
    "self_confidence": ("Confianza", CONFIDENCE),
}


snapshots = sa.table(
    "training_snapshots",
    sa.column("id", sa.BigInteger),
    sa.column("sync_id", sa.BigInteger),
    sa.column("team_id", sa.BigInteger),
    sa.column("captured_at", sa.DateTime(timezone=True)),
    sa.column("training_type", sa.SmallInteger),
    sa.column("training_level", sa.SmallInteger),
    sa.column("new_training_level", sa.SmallInteger),
    sa.column("stamina_part", sa.SmallInteger),
    sa.column("last_training_type", sa.SmallInteger),
    sa.column("last_training_level", sa.SmallInteger),
    sa.column("last_stamina_part", sa.SmallInteger),
    sa.column("trainer_ht_id", sa.BigInteger),
    sa.column("trainer_name", sa.String),
    sa.column("morale", sa.SmallInteger),
    sa.column("self_confidence", sa.SmallInteger),
    sa.column("formation_xp_json", sa.String),
    sa.column("content_hash", sa.LargeBinary),
)

teams = sa.table(
    "teams",
    sa.column("id", sa.BigInteger),
    sa.column("ht_team_id", sa.BigInteger),
)

changes = sa.table(
    "sync_changes",
    sa.column("id", sa.BigInteger),
    sa.column("sync_id", sa.BigInteger),
    sa.column("team_id", sa.BigInteger),
    sa.column("category", sa.String),
    sa.column("summary", sa.String),
    sa.column("detail_json", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def _formation_xp(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("formation_xp_json historico no contiene un objeto JSON")
    return value


def _payload(row: Any, morale: int | None, confidence: int | None) -> dict[str, Any]:
    return {
        "ht_team_id": row["ht_team_id"],
        "training_type": row["training_type"],
        "training_level": row["training_level"],
        "new_training_level": row["new_training_level"],
        "stamina_part": row["stamina_part"],
        "last_training_type": row["last_training_type"],
        "last_training_level": row["last_training_level"],
        "last_stamina_part": row["last_stamina_part"],
        "trainer_ht_id": row["trainer_ht_id"],
        "trainer_name": row["trainer_name"],
        "morale": morale,
        "self_confidence": confidence,
        "formation_xp": _formation_xp(row["formation_xp_json"]),
    }


def _hash(payload: dict[str, Any]) -> bytes:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).digest()


def _metric_of_change(row: Any) -> str | None:
    detail_raw = row["detail_json"]
    if detail_raw:
        try:
            detail = json.loads(detail_raw)
        except (TypeError, ValueError):
            detail = None
        if isinstance(detail, dict) and detail.get("metric") in PSYCHOLOGY:
            return str(detail["metric"])

    summary = row["summary"] or ""
    if summary.startswith("Espíritu del equipo:"):
        return "morale"
    if summary.startswith("Confianza:"):
        return "self_confidence"
    return None


def _is_placeholder_change(row: Any, metric: str | None) -> bool:
    if metric is None:
        return False
    detail_raw = row["detail_json"]
    if detail_raw:
        try:
            detail = json.loads(detail_raw)
        except (TypeError, ValueError):
            detail = None
        if isinstance(detail, dict) and (detail.get("before") == -1 or detail.get("after") == -1):
            return True
    return "-1" in (row["summary"] or "")


def _change_payload(
    metric: str,
    before: int,
    after: int,
) -> tuple[str, str]:
    label, names = PSYCHOLOGY[metric]
    before_label = names.get(before, str(before))
    after_label = names.get(after, str(after))
    summary = f"{label}: {before_label} -> {after_label}"
    detail = {
        "metric": metric,
        "label": label,
        "before": before,
        "after": after,
        "beforeLabel": before_label,
        "afterLabel": after_label,
        "kind": "level",
        "good": after > before,
    }
    return summary, json.dumps(detail, ensure_ascii=False)


def _clean_history(bind: Connection) -> None:
    rows = list(
        bind.execute(
            sa.select(
                snapshots,
                teams.c.ht_team_id.label("ht_team_id"),
            )
            .select_from(snapshots.join(teams, snapshots.c.team_id == teams.c.id))
            .order_by(
                snapshots.c.team_id,
                snapshots.c.captured_at,
                snapshots.c.id,
            )
        ).mappings()
    )

    last_valid: dict[int, dict[str, int]] = {}
    previous_effective: dict[int, dict[str, int | None]] = {}
    expected_changes: list[dict[str, Any]] = []
    planned_updates: list[tuple[Any, dict[str, int | None], bytes, bytes]] = []

    # Preflight completo: si una sola foto no es reconstruible, no se toca
    # ninguna. Es especialmente importante en SQLite, donde Alembic no puede
    # prometer transacciones para todas las operaciones DDL.
    for row in rows:
        old_hash = bytes(row["content_hash"])
        if _hash(_payload(row, row["morale"], row["self_confidence"])) != old_hash:
            raise RuntimeError(
                f"El snapshot de entrenamiento {row['id']} no coincide con su content_hash"
            )

        team_id = int(row["team_id"])
        state = last_valid.setdefault(team_id, {})
        updates: dict[str, int | None] = {}
        effective: dict[str, int | None] = {}
        for field in PSYCHOLOGY:
            value = row[field]
            if isinstance(value, int) and value >= 0:
                state[field] = value
                effective[field] = value
            else:
                effective[field] = state.get(field)
                if value == -1:
                    updates[field] = effective[field]

        if updates:
            new_morale = updates.get("morale", row["morale"])
            new_confidence = updates.get("self_confidence", row["self_confidence"])
            new_hash = _hash(_payload(row, new_morale, new_confidence))
            planned_updates.append((row, updates, old_hash, new_hash))

        previous = previous_effective.get(team_id)
        if previous is not None:
            for metric in PSYCHOLOGY:
                before = previous[metric]
                after = effective[metric]
                if before is not None and after is not None and before != after:
                    expected_changes.append(
                        {
                            "sync_id": row["sync_id"],
                            "team_id": team_id,
                            "metric": metric,
                            "before": before,
                            "after": after,
                            "created_at": row["captured_at"],
                        }
                    )
        previous_effective[team_id] = effective

    for row, updates, old_hash, new_hash in planned_updates:
        result = bind.execute(
            snapshots.update()
            .where(
                snapshots.c.id == row["id"],
                snapshots.c.content_hash == old_hash,
            )
            .values(**updates, content_hash=new_hash)
        )
        if result.rowcount != 1:
            raise RuntimeError(f"No se pudo limpiar el snapshot {row['id']}")

    historical_changes = list(
        bind.execute(sa.select(changes).where(changes.c.category == "entrenamiento")).mappings()
    )
    delete_ids: list[int] = []
    existing: set[tuple[int, str]] = set()
    for row in historical_changes:
        metric = _metric_of_change(row)
        if _is_placeholder_change(row, metric):
            delete_ids.append(int(row["id"]))
        elif metric is not None:
            existing.add((int(row["sync_id"]), metric))

    if delete_ids:
        bind.execute(changes.delete().where(changes.c.id.in_(delete_ids)))

    for item in expected_changes:
        key = (int(item["sync_id"]), str(item["metric"]))
        if key in existing:
            continue
        summary, detail_json = _change_payload(
            str(item["metric"]),
            int(item["before"]),
            int(item["after"]),
        )
        bind.execute(
            changes.insert().values(
                sync_id=item["sync_id"],
                team_id=item["team_id"],
                category="entrenamiento",
                summary=summary,
                detail_json=detail_json,
                created_at=item["created_at"],
            )
        )
        existing.add(key)

    remaining_snapshots = bind.scalar(
        sa.select(sa.func.count())
        .select_from(snapshots)
        .where(
            sa.or_(
                snapshots.c.morale == -1,
                snapshots.c.self_confidence == -1,
            )
        )
    )
    if remaining_snapshots:
        raise RuntimeError("Quedaron placeholders -1 en training_snapshots")

    for row in bind.execute(
        sa.select(changes).where(changes.c.category == "entrenamiento")
    ).mappings():
        metric = _metric_of_change(row)
        if _is_placeholder_change(row, metric):
            raise RuntimeError("Quedaron cambios psicologicos historicos con -1")


def upgrade() -> None:
    _clean_history(op.get_bind())


def downgrade() -> None:
    # La ausencia temporal no vuelve a ser un nivel al bajar una revision.
    # Esta limpieza de datos es deliberadamente irreversible.
    pass
