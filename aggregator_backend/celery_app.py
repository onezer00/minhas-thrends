import os
from celery import Celery
from celery.schedules import crontab
from aggregator_backend.config import BROKER_URL, BACKEND_URL

# Cria a instância do Celery
celery = Celery("aggregator", broker=BROKER_URL, backend=BACKEND_URL)

# Atualiza as configurações do Celery
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Configura o agendamento das tasks com Celery Beat
celery.conf.beat_schedule = {
    "update-twitter-every-8-hours": {
        "task": "aggregator_backend.tasks.fetch_twitter_data",
        "schedule": crontab(minute=0, hour="*/8"),
        "args": ("python",),
    },
    "update-youtube-every-1-hour": {
        "task": "aggregator_backend.tasks.fetch_youtube_data",
        "schedule": crontab(minute=0, hour="*"),
        "args": ("python",),
    },
    "update-reddit-every-1-hour": {
        "task": "aggregator_backend.tasks.fetch_reddit_data",
        "schedule": crontab(minute=0, hour="*"),
        "args": ("python",),
    },
}

# Descobre automaticamente as tasks definidas no pacote aggregator_backend
celery.autodiscover_tasks(["aggregator_backend"])
