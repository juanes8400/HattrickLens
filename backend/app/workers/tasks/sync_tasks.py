"""Tasks Celery de sincronización. Cadena secuencial por usuario (regla CHPP)."""

from typing import Any

from app.workers.celery_app import celery


@celery.task(name="sync.sync_team", bind=True, max_retries=3, retry_backoff=True)
def sync_team_task(
    self: Any, user_id: int, team_id: int, files: list[str] | None = None
) -> dict[str, Any]:
    """Ejecuta SyncTeamHandler con deps reales. Progreso → Redis pub/sub → SSE."""
    # Pseudocódigo de wiring (async runner):
    # uow = SqlAlchemyUnitOfWork(SessionLocal)
    # token = decrypt_chpp_token(user_id)
    # chpp = CHPPClient(token.oauth_token, token.oauth_secret)
    # sync_id = run(SyncTeamHandler(uow, chpp).execute(SyncTeamCommand(...)))
    # publish_progress(self.request.id, "completed")
    return {"userId": user_id, "teamId": team_id, "status": "todo"}


@celery.task(name="compute.maintain_partitions")
def maintain_partitions() -> None:
    """Crea particiones mensuales futuras de las tablas de snapshots."""
