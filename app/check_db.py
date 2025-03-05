import os
import sys
import time
import logging
import argparse
import redis
from sqlalchemy import create_engine, text

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def check_env_vars():
    """Verifica se todas as variáveis de ambiente necessárias estão configuradas"""
    required_vars = [
        'DATABASE_URL',
        'CELERY_BROKER_URL',
        'CELERY_RESULT_BACKEND'
    ]
    
    optional_vars = [
        'YOUTUBE_API_KEY',
        'REDDIT_CLIENT_ID',
        'REDDIT_SECRET',
        'REDDIT_USERNAME',
        'REDDIT_PASSWORD'
    ]
    
    missing_required = []
    missing_optional = []
    
    # Verifica variáveis obrigatórias
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_required.append(var)
            logger.error(f"Variável de ambiente obrigatória não configurada: {var}")
        else:
            # Não loga valores completos para não expor credenciais
            if 'URL' in var or 'PASSWORD' in var or 'SECRET' in var or 'KEY' in var:
                logger.info(f"Variável de ambiente {var} está configurada")
            else:
                logger.info(f"Variável de ambiente {var} = {value}")
    
    # Verifica variáveis opcionais
    for var in optional_vars:
        value = os.getenv(var)
        if not value:
            missing_optional.append(var)
            logger.warning(f"Variável de ambiente opcional não configurada: {var}")
        else:
            logger.info(f"Variável de ambiente {var} está configurada")
    
    if missing_required:
        logger.error(f"Faltam variáveis de ambiente obrigatórias: {', '.join(missing_required)}")
        return False
    
    if missing_optional:
        logger.warning(f"Faltam variáveis de ambiente opcionais: {', '.join(missing_optional)}")
    
    return True

def check_redis_connection():
    """Verifica a conexão com o Redis e tenta diferentes URLs"""
    # Lista de possíveis URLs para o Redis
    redis_urls = [
        os.getenv('CELERY_BROKER_URL'),
        os.getenv('CELERY_RESULT_BACKEND'),
        os.getenv('REDIS_URL'),
        os.getenv('REDIS_TLS_URL'),
        'redis://trendpulse-redis.internal:6379/0',
        'redis://trendpulse-redis:6379/0',
        'redis://localhost:6379/0'
    ]
    
    # Filtra URLs vazias ou None
    redis_urls = [url for url in redis_urls if url]
    
    if not redis_urls:
        logger.error("Nenhuma URL de Redis encontrada nas variáveis de ambiente")
        return False
    
    for url in redis_urls:
        # Extrai apenas o host e porta para o log (sem credenciais)
        safe_url = url
        if '@' in url:
            safe_url = url.split('@')[1]
        
        logger.info(f"Tentando conectar ao Redis: {safe_url}")
        
        try:
            client = redis.from_url(url)
            ping_result = client.ping()
            logger.info(f"Conexão com Redis bem-sucedida! Ping: {ping_result}")
            
            # Atualiza a variável de ambiente se não for a URL principal
            if url != os.getenv('CELERY_BROKER_URL'):
                logger.info(f"Atualizando CELERY_BROKER_URL para URL que funcionou: {safe_url}")
                os.environ['CELERY_BROKER_URL'] = url
                os.environ['CELERY_RESULT_BACKEND'] = url
            
            return True
        except Exception as e:
            logger.warning(f"Falha ao conectar ao Redis em {safe_url}: {str(e)}")
    
    logger.error("Não foi possível conectar a nenhuma URL do Redis")
    return False

def check_database_connection(max_attempts=5, wait_time=5):
    """Verifica a conexão com o banco de dados"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("Variável DATABASE_URL não configurada")
        return False
    
    # Não loga a URL completa para não expor credenciais
    safe_url = database_url
    if '@' in database_url:
        safe_url = database_url.split('@')[1]
    
    logger.info(f"Tentando conectar ao banco de dados: {safe_url}")
    
    for attempt in range(max_attempts):
        try:
            engine = create_engine(database_url)
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                logger.info(f"Conexão com banco de dados bem-sucedida! Resultado: {result.fetchone()}")
                return True
        except Exception as e:
            logger.warning(f"Tentativa {attempt+1}/{max_attempts} falhou: {str(e)}")
            if attempt < max_attempts - 1:
                logger.info(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
                time.sleep(wait_time)
    
    logger.error(f"Não foi possível conectar ao banco de dados após {max_attempts} tentativas")
    return False

def main():
    parser = argparse.ArgumentParser(description='Verifica conexões com banco de dados e Redis')
    parser.add_argument('--max-attempts', type=int, default=5, help='Número máximo de tentativas de conexão')
    parser.add_argument('--wait-time', type=int, default=5, help='Tempo de espera entre tentativas (segundos)')
    parser.add_argument('--skip-db', action='store_true', help='Pula a verificação do banco de dados')
    args = parser.parse_args()
    
    logger.info("Iniciando verificação de ambiente e conexões")
    
    # Verifica variáveis de ambiente
    if not check_env_vars():
        logger.warning("Algumas variáveis de ambiente obrigatórias não estão configuradas")
    
    # Verifica conexão com Redis
    redis_ok = check_redis_connection()
    if not redis_ok:
        logger.error("Falha na conexão com Redis")
        sys.exit(1)
    
    # Verifica conexão com banco de dados (se não for pulada)
    if not args.skip_db:
        db_ok = check_database_connection(args.max_attempts, args.wait_time)
        if not db_ok:
            logger.error("Falha na conexão com banco de dados")
            sys.exit(1)
    
    logger.info("Todas as verificações concluídas com sucesso!")
    sys.exit(0)

if __name__ == "__main__":
    main()