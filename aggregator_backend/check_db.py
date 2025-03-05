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

def check_redis_connection():
    """Verifica a conexão com o Redis e tenta ajustar a URL se necessário."""
    import redis
    import os
    import time
    
    broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    logger.info(f"Tentando conectar ao Redis usando: {broker_url}")
    
    # Lista de possíveis URLs para tentar
    urls_to_try = [
        broker_url,
        broker_url.replace('redis://', 'redis://trendpulse-redis:6379/'),
        broker_url.replace('redis://', 'redis://trendpulse-redis.internal:6379/'),
        broker_url.replace('redis://', 'redis://trendpulse-redis.onrender.com:6379/'),
        'redis://trendpulse-redis.internal:6379/0',
        'redis://trendpulse-redis:6379/0',
        'redis://trendpulse-redis.onrender.com:6379/0',
        'redis://localhost:6379/0'
    ]
    
    # Remover duplicatas
    urls_to_try = list(dict.fromkeys(urls_to_try))
    
    # Tentar cada URL
    for url in urls_to_try:
        try:
            logger.info(f"Tentando conectar ao Redis com URL: {url}")
            client = redis.Redis.from_url(url)
            ping_result = client.ping()
            logger.info(f"Conexão com Redis bem-sucedida usando {url}! Ping: {ping_result}")
            
            # Se a URL for diferente da original, atualizar as variáveis de ambiente
            if url != broker_url:
                logger.info(f"Atualizando variáveis de ambiente para usar a URL do Redis: {url}")
                os.environ['CELERY_BROKER_URL'] = url
                os.environ['CELERY_RESULT_BACKEND'] = url
                
                # Tentar atualizar também a configuração do Celery se estiver disponível
                try:
                    from celery import current_app
                    current_app.conf.broker_url = url
                    current_app.conf.result_backend = url
                    logger.info("Configuração do Celery atualizada com a nova URL do Redis")
                except:
                    pass
            
            return True
        except Exception as e:
            logger.warning(f"Falha ao conectar ao Redis usando {url}: {str(e)}")
    
    logger.error("Não foi possível conectar ao Redis usando nenhuma das URLs tentadas")
    return False

def check_database_connection():
    """Verifica a conexão com o banco de dados."""
    import os
    from sqlalchemy import create_engine
    
    database_url = os.environ.get('DATABASE_URL')
    logger.info(f"Verificando conexão com o banco de dados: {database_url}")
    
    # Se for uma URL MySQL, certifique-se de que está usando o driver pymysql
    if database_url and database_url.startswith('mysql://'):
        database_url = database_url.replace('mysql://', 'mysql+pymysql://')
        logger.info(f"URL ajustada para usar pymysql: {database_url}")
    
    try:
        engine = create_engine(database_url)
        connection = engine.connect()
        connection.close()
        logger.info("Conexão com o banco de dados bem-sucedida!")
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return False
        
        # Tenta conectar e executar uma consulta simples
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info(f"Conexão bem-sucedida! Resultado: {result.fetchone()}")
            
            # Verifica informações do banco de dados
            try:
                db_info = connection.execute(text("SELECT VERSION()"))
                logger.info(f"Versão do banco de dados: {db_info.fetchone()}")
            except Exception as e:
                logger.warning(f"Não foi possível obter a versão do banco: {str(e)}")
            
        return True
    
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        logger.error(f"URL do banco: {database_url}")
        return False

if __name__ == "__main__":
    # Configuração dos argumentos de linha de comando
    parser = argparse.ArgumentParser(description='Verifica a conexão com o banco de dados e Redis.')
    parser.add_argument('--max-attempts', type=int, default=5, 
                        help='Número máximo de tentativas de conexão')
    parser.add_argument('--wait-time', type=int, default=5, 
                        help='Tempo de espera em segundos entre tentativas')
    parser.add_argument('--skip-redis', action='store_true',
                        help='Pula a verificação do Redis')
    parser.add_argument('--skip-db', action='store_true',
                        help='Pula a verificação do banco de dados')
    args = parser.parse_args()
    
    max_attempts = args.max_attempts
    wait_time = args.wait_time
    
    logger.info(f"Iniciando verificação de conexões...")
    logger.info(f"Máximo de tentativas: {max_attempts}, tempo de espera: {wait_time}s")
    
    # Verifica Redis se não for pulado
    redis_ok = True
    if not args.skip_redis:
        redis_attempt = 0
        redis_ok = False
        
        while redis_attempt < max_attempts and not redis_ok:
            redis_attempt += 1
            logger.info(f"Tentativa {redis_attempt} de {max_attempts} para Redis...")
            
            if check_redis_connection():
                logger.info("Conexão com Redis estabelecida com sucesso!")
                redis_ok = True
                break
            
            if redis_attempt < max_attempts:
                logger.info(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
                time.sleep(wait_time)
        
        if not redis_ok:
            logger.error(f"Falha ao conectar ao Redis após {max_attempts} tentativas.")
    
    # Verifica banco de dados se não for pulado
    db_ok = True
    if not args.skip_db:
        db_attempt = 0
        db_ok = False
        
        while db_attempt < max_attempts and not db_ok:
            db_attempt += 1
            logger.info(f"Tentativa {db_attempt} de {max_attempts} para banco de dados...")
            
            if check_database_connection():
                logger.info("Conexão com banco de dados estabelecida com sucesso!")
                db_ok = True
                break
            
            if db_attempt < max_attempts:
                logger.info(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
                time.sleep(wait_time)
        
        if not db_ok:
            logger.error(f"Falha ao conectar ao banco de dados após {max_attempts} tentativas.")
    
    # Verifica o resultado final
    if (args.skip_redis or redis_ok) and (args.skip_db or db_ok):
        logger.info("Verificação de conexões concluída com sucesso!")
        sys.exit(0)
    else:
        logger.error("Falha na verificação de conexões.")
        sys.exit(1)