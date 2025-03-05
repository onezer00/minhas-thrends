import os
from celery import Celery
from celery.schedules import crontab
import logging
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Configurações do Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Cria a instância do Celery
celery = Celery(
    "aggregator_backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Configurações do Celery
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Aumentar o pool de conexões para o Redis
    broker_pool_limit=20,  # Aumentado de 10
    redis_max_connections=40,  # Aumentado de 20
    
    # Configurações de retry mais robustas
    broker_transport_options={
        'retry_policy': {
            'timeout': 10.0,  # Aumentado de 5.0
            'max_retries': 5,  # Aumentado de 3
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 1.0,  # Aumentado de 0.5
        },
        'visibility_timeout': 43200,
    },
    
    # Configurações de retry para tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=1800,
    
    # Configurações de pool de conexões do Redis
    broker_pool_limit=10,
    redis_max_connections=20,
    
    # Configurações de heartbeat
    broker_heartbeat=10,
    broker_connection_retry=True,
    broker_connection_max_retries=0,
)

# Configura o agendamento das tasks com Celery Beat
celery.conf.beat_schedule = {
    # Tarefa principal para buscar todas as tendências a cada 2 horas
    "fetch-all-trends-every-2-hours": {
        "task": "aggregator_backend.tasks.fetch_all_trends",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    # Tarefas específicas para cada plataforma
    "update-twitter-every-3-hours": {
        "task": "aggregator_backend.tasks.fetch_twitter_trends",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "update-youtube-every-3-hours": {
        "task": "aggregator_backend.tasks.fetch_youtube_trends",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "update-reddit-every-2-hours": {
        "task": "aggregator_backend.tasks.fetch_reddit_trends",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Limpeza de tendências antigas uma vez por dia
    "clean-old-trends-daily": {
        "task": "aggregator_backend.tasks.clean_old_trends",
        "schedule": crontab(minute=0, hour=3),  # 3 AM
    },
}

# Configura os pacotes onde o Celery deve procurar por tasks
celery.autodiscover_tasks(['aggregator_backend'])

# Verifica se o banco de dados está vazio na inicialização
@celery.on_after_configure.connect
def setup_initial_tasks(sender, **kwargs):
    """
    Função que verifica se o banco está vazio e, em caso positivo,
    dispara a busca de tendências imediatamente.
    """
    try:
        # Importa os modelos e conexão com o banco
        from aggregator_backend.models import SessionLocal, Trend
        
        # Cria uma sessão
        db = SessionLocal()
        
        # Verifica se existem tendências no banco
        trend_count = db.query(func.count(Trend.id)).scalar()
        
        # Fecha a sessão
        db.close()
        
        if trend_count == 0:
            logger.info("Banco de dados vazio. Iniciando busca inicial de tendências...")
            # Dispara as tarefas de busca de tendências imediatamente
            from aggregator_backend.tasks import fetch_all_trends
            fetch_all_trends.delay()
        else:
            logger.info(f"Banco de dados contém {trend_count} tendências. Seguindo agendamento normal.")
            
    except Exception as e:
        logger.error(f"Erro ao verificar o banco de dados: {str(e)}")


if __name__ == "__main__":
    celery.start()