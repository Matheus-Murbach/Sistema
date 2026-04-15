from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "sistema",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.nfe_tasks",
        "app.tasks.notificacao_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_routes={
        "app.tasks.nfe_tasks.*": {"queue": "nfe"},
        "app.tasks.notificacao_tasks.*": {"queue": "notificacoes"},
    },
)
