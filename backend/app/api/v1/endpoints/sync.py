from fastapi import APIRouter

router = APIRouter()


@router.get("/{job_id}")
async def get_sync_status(job_id: str) -> dict[str, str]:
    from app.workers.celery_app import celery

    res = celery.AsyncResult(job_id)
    return {"jobId": job_id, "status": res.status.lower()}

# TODO: GET /{job_id}/events → SSE (sse-starlette) suscrito a Redis pub/sub del progreso
