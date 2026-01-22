"""
Celery application configuration.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "lora_person",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.cpu.tasks",
        "app.workers.gpu.tasks",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600 * 2,  # 2 hours max
    worker_prefetch_multiplier=1,
)

# Route tasks to dedicated queues so you can run separate workers:
# - CPU worker: -Q cpu_tasks
# - GPU worker: -Q gpu_tasks
celery_app.conf.task_routes = {
    "cpu.*": {"queue": "cpu_tasks"},
    "gpu.*": {"queue": "gpu_tasks"},
}
