from celery import Celery

from app.core.config import settings

celery = Celery(
    "hattrick_lens",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks.sync_tasks"],
)

celery.conf.update(
    task_routes={
        "sync.*": {"queue": "sync"},
        "compute.*": {"queue": "compute"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    beat_schedule={
        # Solo mantenimiento interno — NUNCA fetch CHPP por timer (regla CHPP)
        "create-partitions": {
            "task": "compute.maintain_partitions",
            "schedule": 86400.0,
        },
    },
)
