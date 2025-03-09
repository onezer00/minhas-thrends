import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, beat_init, task_success, task_failure, task_revoked
import time
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import tempfile
import shutil

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def get_redis_broker_url():
    """
    Determina dinamicamente a URL do broker Redis.
    Tenta várias opções em ordem de prioridade.
    """
    # Opções de URLs para o broker
    broker_urls = [
        os.getenv('CELERY_BROKER_URL'),
        os.getenv('REDIS_URL'),
        os.getenv('REDIS_TLS_URL'),
        'redis://localhost:6379/0'
    ]
    
    # Filtra URLs vazias ou None
    valid_urls = [url for url in broker_urls if url]
    
    if not valid_urls:
        logger.warning("Nenhuma URL válida de Redis encontrada nas variáveis de ambiente. Usando fallback local.")
        return 'redis://localhost:6379/0'
    
    selected_url = valid_urls[0]
    logger.info(f"Usando broker Redis: {selected_url}")
    return selected_url

# Obtém a URL do broker
broker_url = get_redis_broker_url()

# Configuração do Celery
celery = Celery(
    'app',
    broker=broker_url,
    backend=broker_url,
    include=['app.tasks']
)

# Configuração do diretório para o arquivo de agendamento do celerybeat
beat_schedule_dir = os.environ.get('CELERY_BEAT_SCHEDULE_DIR', '/tmp/celerybeat')
beat_schedule_file = os.path.join(beat_schedule_dir, 'celerybeat-schedule')

# Verifica se o diretório existe e tem permissões de escrita
try:
    if not os.path.exists(beat_schedule_dir):
        os.makedirs(beat_schedule_dir, exist_ok=True)
        logger.info(f"Diretório para celerybeat criado: {beat_schedule_dir}")
    
    # Testa permissões de escrita
    test_file = os.path.join(beat_schedule_dir, 'test_write')
    with open(test_file, 'w') as f:
        f.write('test')
    os.remove(test_file)
    logger.info(f"Diretório {beat_schedule_dir} tem permissões de escrita")
except Exception as e:
    logger.error(f"Erro ao configurar diretório para celerybeat: {e}")
    # Fallback para diretório temporário padrão
    beat_schedule_dir = '/tmp'
    beat_schedule_file = os.path.join(beat_schedule_dir, 'celerybeat-schedule')
    logger.info(f"Usando diretório fallback para celerybeat: {beat_schedule_dir}")

# Configurações do Celery
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    worker_max_tasks_per_child=200,  # Reinicia o worker após 200 tarefas para liberar memória
    worker_prefetch_multiplier=1,    # Reduz o número de tarefas pré-buscadas
    broker_pool_limit=5,             # Limita o número de conexões no pool do broker
    redis_max_connections=10,        # Limita o número máximo de conexões Redis
    result_expires=60 * 60 * 24,      # 1 dia em vez de 3
    beat_schedule_filename=beat_schedule_file,  # Arquivo de agendamento do celerybeat
    beat_max_loop_interval=300,      # Intervalo máximo entre verificações de agendamento
    broker_connection_retry=True,    # Configuração para lidar com reconexões após "adormecimento"
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_connection_timeout=30,
    worker_concurrency=2,             # Reduz a concorrência para economizar recursos
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

# Sinal executado quando o Beat é inicializado
@beat_init.connect
def on_beat_init(sender, **kwargs):
    logger.info("Beat inicializado!")
    
    # Verifica se o diretório temporário existe e tem permissões corretas
    try:
        # Garante que o diretório existe
        os.makedirs(beat_schedule_dir, exist_ok=True)
        
        # Verifica se o arquivo de agendamento existe
        if os.path.exists(beat_schedule_file):
            # Verifica permissões
            if not os.access(beat_schedule_file, os.W_OK):
                logger.warning(f"Arquivo {beat_schedule_file} não tem permissão de escrita. Tentando corrigir...")
                
                # Tenta remover o arquivo existente
                try:
                    os.remove(beat_schedule_file)
                    logger.info(f"Arquivo {beat_schedule_file} removido com sucesso.")
                except Exception as e:
                    logger.error(f"Erro ao remover arquivo {beat_schedule_file}: {str(e)}")
                    
                    # Tenta criar um novo arquivo em um local diferente
                    new_path = os.path.join(beat_schedule_dir, f"celerybeat-{os.getpid()}")
                    logger.info(f"Tentando usar novo caminho: {new_path}")
                    celery.conf.beat_schedule_filename = new_path
        
        logger.info(f"Beat usando arquivo de agendamento: {celery.conf.beat_schedule_filename}")
    except Exception as e:
        logger.error(f"Erro ao configurar diretório do Beat: {str(e)}")
        
        # Tenta usar um caminho alternativo como último recurso
        fallback_path = os.path.join(beat_schedule_dir, f"celerybeat-{os.getpid()}")
        logger.info(f"Usando caminho alternativo para o Beat: {fallback_path}")
        celery.conf.beat_schedule_filename = fallback_path

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

# Handlers para sinais do Celery para logging
@task_success.connect
def task_success_handler(sender=None, **kwargs):
    logger.info(f"Tarefa {sender.name} concluída com sucesso")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    logger.error(f"Tarefa {sender.name} falhou: {exception}")

@task_revoked.connect
def task_revoked_handler(sender=None, request=None, **kwargs):
    logger.warning(f"Tarefa {sender.name} foi revogada")

if __name__ == "__main__":
    celery.start()