import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready
import time
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import tempfile

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Função para obter a URL do broker com fallbacks
def get_broker_url():
    # Tenta obter a URL do broker da variável de ambiente
    broker_url = os.environ.get('CELERY_BROKER_URL')
    
    # Se estamos no Render, tenta diferentes formatos de URL
    if os.environ.get('RENDER'):
        # Lista de possíveis URLs para tentar
        possible_urls = [
            broker_url,
            broker_url.replace('redis://', 'redis://default:@') if broker_url else None,
            f"redis://trendpulse-redis.internal:6379/0",
            f"redis://trendpulse-redis:6379/0",
            "redis://localhost:6379/0"
        ]
        
        # Filtra URLs None
        possible_urls = [url for url in possible_urls if url]
        
        # Tenta cada URL
        for url in possible_urls:
            try:
                logger.info(f"Tentando conectar ao Redis em: {url}")
                # Importa aqui para evitar dependência circular
                import redis
                r = redis.from_url(url)
                r.ping()
                logger.info(f"Conexão bem-sucedida com Redis em: {url}")
                return url
            except Exception as e:
                logger.warning(f"Falha ao conectar ao Redis em {url}: {str(e)}")
                continue
    
    # Se nenhuma URL funcionou ou não estamos no Render, retorna a URL original
    return broker_url or "redis://localhost:6379/0"

# Obtém as URLs para broker e backend
broker_url = get_broker_url()
result_backend = broker_url

logger.info(f"Usando broker URL: {broker_url}")
logger.info(f"Usando result backend: {result_backend}")

# Define o diretório temporário para o arquivo de agendamento do Beat
temp_dir = tempfile.gettempdir()
beat_schedule_path = os.path.join(temp_dir, "celerybeat-schedule")
logger.info(f"Arquivo de agendamento do Beat será salvo em: {beat_schedule_path}")

# Configuração do Celery
celery = Celery(
    'app',
    broker=broker_url,
    backend=result_backend,
    include=['app.tasks'],
)

# Configurações para limitar o número de conexões ao Redis e otimizar memória
celery.conf.update(
    # Configurações de conexão Redis
    broker_pool_limit=3,  # Reduzido para economizar memória
    redis_max_connections=5,  # Reduzido para economizar memória
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,
    
    # Configurações para otimizar memória
    worker_prefetch_multiplier=1,  # Reduz o número de tarefas pré-carregadas
    worker_max_tasks_per_child=50,  # Reinicia o worker após 50 tarefas para liberar memória
    worker_max_memory_per_child=400000,  # Limita a 400MB por processo filho
    task_time_limit=1800,  # Limita o tempo de execução de tarefas a 30 minutos
    task_soft_time_limit=1500,  # Aviso de tempo limite suave em 25 minutos
    
    # Configurações de concorrência
    worker_concurrency=1,  # Apenas um processo worker para economizar memória
    
    # Configurações de resultado
    result_expires=3600,  # Resultados expiram após 1 hora
    
    # Configurações de retry
    result_backend_transport_options={
        'retry_policy': {
            'interval_start': 0,
            'interval_step': 1,
            'interval_max': 5,
            'max_retries': 10,
        }
    },
    
    # Configuração do Beat
    beat_schedule_filename=beat_schedule_path,  # Usa diretório temporário
    beat_max_loop_interval=300,  # Máximo de 5 minutos entre verificações
)

# Configuração para o Flower
celery.conf.update(
    flower_url_prefix='',
    flower_persistent=False,
    flower_db=None,
    flower_max_tasks=10000,
    flower_port=os.environ.get('PORT', 5555),
)

# Sinal executado quando o worker está pronto
@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    logger.info("Worker pronto e conectado ao Redis!")
    
    # Limpa a memória
    import gc
    gc.collect()
    logger.info("Coleta de lixo executada para liberar memória")

# Configuração para tarefas periódicas (beat)
celery.conf.beat_schedule = {
    'fetch-youtube-trends-every-3-hours': {
        'task': 'app.tasks.fetch_youtube_trends',
        'schedule': 60 * 60 * 3,  # A cada 3 horas
    },
    'fetch-reddit-trends-every-2-hours': {
        'task': 'app.tasks.fetch_reddit_trends',
        'schedule': 60 * 60 * 2,  # A cada 2 horas
    },
    'clean-old-trends-daily': {
        'task': 'app.tasks.clean_old_trends',
        'schedule': 60 * 60 * 24,  # Diariamente
    },
}

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