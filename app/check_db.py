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

def check_redis_connection(max_attempts=5, wait_time=5):
    """
    Verifica a conexão com o Redis, tentando várias URLs possíveis.
    
    Args:
        max_attempts: Número máximo de tentativas para cada URL
        wait_time: Tempo de espera entre tentativas em segundos
        
    Returns:
        bool: True se a conexão for bem-sucedida, False caso contrário
    """
    # Obtém a URL do Redis da variável de ambiente
    redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    
    # Lista de possíveis URLs para tentar
    possible_urls = [
        redis_url,
        redis_url.replace('redis://', 'redis://default:@') if redis_url else None,
        "redis://trendpulse-redis.internal:6379/0",
        "redis://trendpulse-redis:6379/0",
        "redis://localhost:6379/0"
    ]
    
    # Filtra URLs None
    possible_urls = [url for url in possible_urls if url]
    
    # Tenta cada URL
    for url in possible_urls:
        logger.info(f"Tentando conectar ao Redis em: {url}")
        
        for attempt in range(1, max_attempts + 1):
            try:
                r = redis.from_url(url)
                r.ping()
                logger.info(f"Conexão bem-sucedida com Redis em: {url}")
                
                # Atualiza a variável de ambiente se a URL for diferente
                if url != redis_url:
                    logger.info(f"Atualizando variável de ambiente CELERY_BROKER_URL para {url}")
                    os.environ["CELERY_BROKER_URL"] = url
                    os.environ["CELERY_RESULT_BACKEND"] = url
                
                return True
            except redis.exceptions.ConnectionError as e:
                logger.warning(f"Tentativa {attempt}/{max_attempts} falhou para {url}: {str(e)}")
                if attempt < max_attempts:
                    logger.info(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
                    time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Erro ao conectar ao Redis em {url}: {str(e)}")
                break
    
    logger.error("Todas as tentativas de conexão com Redis falharam.")
    return False

def check_database_connection(max_attempts=5, wait_time=5):
    """
    Verifica a conexão com o banco de dados.
    
    Args:
        max_attempts: Número máximo de tentativas
        wait_time: Tempo de espera entre tentativas em segundos
        
    Returns:
        bool: True se a conexão for bem-sucedida, False caso contrário
    """
    # Obtém a URL do banco de dados da variável de ambiente
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        logger.error("Variável de ambiente DATABASE_URL não definida.")
        return False
    
    logger.info(f"Tentando conectar ao banco de dados: {db_url.split('@')[0]}@...")
    
    for attempt in range(1, max_attempts + 1):
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Conexão bem-sucedida com o banco de dados.")
            return True
        except Exception as e:
            logger.warning(f"Tentativa {attempt}/{max_attempts} falhou: {str(e)}")
            if attempt < max_attempts:
                logger.info(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
                time.sleep(wait_time)
    
    logger.error("Todas as tentativas de conexão com o banco de dados falharam.")
    return False

def main():
    """
    Função principal para verificar as conexões com o banco de dados e Redis.
    """
    parser = argparse.ArgumentParser(description="Verifica conexões com banco de dados e Redis")
    parser.add_argument("--max-attempts", type=int, default=5, help="Número máximo de tentativas")
    parser.add_argument("--wait-time", type=int, default=5, help="Tempo de espera entre tentativas em segundos")
    parser.add_argument("--skip-db", action="store_true", help="Pula a verificação do banco de dados")
    args = parser.parse_args()
    
    # Verifica a conexão com o Redis
    redis_ok = check_redis_connection(args.max_attempts, args.wait_time)
    
    # Verifica a conexão com o banco de dados, se não for para pular
    db_ok = True
    if not args.skip_db:
        db_ok = check_database_connection(args.max_attempts, args.wait_time)
    
    # Retorna código de saída baseado no resultado das verificações
    if redis_ok and db_ok:
        logger.info("Todas as conexões estão funcionando corretamente.")
        return 0
    else:
        logger.error("Falha em uma ou mais conexões.")
        return 1

if __name__ == "__main__":
    exit(main())