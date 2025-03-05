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

# Obtém as URLs do broker e backend do Celery
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Verifica se estamos no Render.com e ajusta as URLs se necessário
if os.environ.get("RENDER", ""):
    # No Render, o nome do serviço Redis pode ser diferente
    redis_service_name = os.environ.get("REDIS_SERVICE_NAME", "")
    if redis_service_name:
        logger.info(f"Detectado ambiente Render com serviço Redis: {redis_service_name}")
        CELERY_BROKER_URL = f"redis://{redis_service_name}:6379/0"
        CELERY_RESULT_BACKEND = f"redis://{redis_service_name}:6379/0"

# Log das URLs que serão usadas
logger.info(f"Celery Broker URL: {CELERY_BROKER_URL}")
logger.info(f"Celery Result Backend: {CELERY_RESULT_BACKEND}")

# Cria a instância do Celery
celery = Celery(
    "app",
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
    # Reduzir o pool de conexões para o Redis para evitar "max number of clients reached"
    broker_pool_limit=5,  # Reduzido de 20
    redis_max_connections=10,  # Reduzido de 40
    
    # Configurações de retry mais robustas
    broker_transport_options={
        'retry_policy': {
            'timeout': 10.0,
            'max_retries': 5,
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 1.0,
        },
        'visibility_timeout': 43200,
    },
    
    # Configurações de retry para tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=1800,
    
    # Configurações de pool de conexões do Redis
    broker_pool_limit=5,  # Reduzido para evitar muitas conexões
    redis_max_connections=10,  # Reduzido para evitar muitas conexões
    
    # Configurações de heartbeat
    broker_heartbeat=10,
    broker_connection_retry=True,
    broker_connection_max_retries=0,
)

# Configura o agendamento das tasks com Celery Beat
celery.conf.beat_schedule = {
    # Tarefa principal para buscar todas as tendências a cada 2 horas
    "fetch-all-trends-every-2-hours": {
        "task": "app.tasks.fetch_all_trends",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    # Tarefas específicas para cada plataforma
    "update-twitter-every-3-hours": {
        "task": "app.tasks.fetch_twitter_trends",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "update-youtube-every-3-hours": {
        "task": "app.tasks.fetch_youtube_trends",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "update-reddit-every-2-hours": {
        "task": "app.tasks.fetch_reddit_trends",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Limpeza de tendências antigas uma vez por dia
    "clean-old-trends-daily": {
        "task": "app.tasks.clean_old_trends",
        "schedule": crontab(minute=0, hour=3),  # 3 AM
    },
}

# Configura os pacotes onde o Celery deve procurar por tasks
celery.autodiscover_tasks(['app'])

# Verifica se o banco de dados está vazio na inicialização
@celery.on_after_configure.connect
def setup_initial_tasks(sender, **kwargs):
    """
    Função que verifica se o banco está vazio e, em caso positivo,
    dispara a busca de tendências imediatamente.
    """
    try:
        # Importa os modelos e conexão com o banco
        from app.models import SessionLocal, Trend
        
        # Cria uma sessão
        db = SessionLocal()
        
        # Verifica se existem tendências no banco
        trend_count = db.query(func.count(Trend.id)).scalar()
        
        # Fecha a sessão
        db.close()
        
        if trend_count == 0:
            logger.info("Banco de dados vazio. Iniciando busca inicial de tendências...")
            # Dispara as tarefas de busca de tendências imediatamente
            from app.tasks import fetch_all_trends
            fetch_all_trends.delay()
        else:
            logger.info(f"Banco de dados contém {trend_count} tendências. Seguindo agendamento normal.")
            
    except Exception as e:
        logger.error(f"Erro ao verificar o banco de dados: {str(e)}")


if __name__ == "__main__":
    celery.start()