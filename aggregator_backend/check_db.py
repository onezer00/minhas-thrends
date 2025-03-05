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
    """
    Verifica a conexão com o Redis e tenta ajustar a URL se necessário.
    """
    broker_url = os.getenv("CELERY_BROKER_URL")
    if not broker_url:
        logger.error("Variável CELERY_BROKER_URL não definida!")
        return False
    
    logger.info(f"Verificando conexão com Redis: {broker_url}")
    
    # Tenta ajustar a URL se estiver usando 'redis' como hostname
    if "redis://" in broker_url and "@redis:" in broker_url:
        # No Render, pode ser necessário usar o nome do serviço completo
        try:
            # Tenta conectar com a URL original
            redis_client = redis.Redis.from_url(broker_url)
            redis_client.ping()
            logger.info("Conexão com Redis estabelecida com sucesso!")
            return True
        except Exception as e:
            logger.warning(f"Erro na conexão original: {str(e)}")
            
            # Tenta com o nome de serviço completo do Render
            try:
                new_url = broker_url.replace("@redis:", "@trendpulse-redis.internal:")
                logger.info(f"Tentando URL alternativa: {new_url}")
                redis_client = redis.Redis.from_url(new_url)
                redis_client.ping()
                logger.info("Conexão com Redis estabelecida com URL alternativa!")
                
                # Atualiza as variáveis de ambiente para o Celery
                os.environ["CELERY_BROKER_URL"] = new_url
                os.environ["CELERY_RESULT_BACKEND"] = new_url
                
                return True
            except Exception as e2:
                logger.error(f"Erro na conexão alternativa: {str(e2)}")
                return False
    
    # Tenta conectar com a URL original
    try:
        redis_client = redis.Redis.from_url(broker_url)
        redis_client.ping()
        logger.info("Conexão com Redis estabelecida com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao Redis: {str(e)}")
        return False

def check_database_connection():
    """
    Verifica a conexão com o banco de dados e imprime informações de diagnóstico.
    """
    # Obtém a URL do banco de dados da variável de ambiente
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        logger.error("Variável DATABASE_URL não definida!")
        return False
    
    logger.info(f"Tentando conectar ao banco de dados: {database_url}")
    
    # Tenta criar o engine e conectar
    try:
        # Para MySQL, adiciona o driver pymysql se necessário
        if "mysql://" in database_url and "pymysql" not in database_url:
            database_url = database_url.replace("mysql://", "mysql+pymysql://")
            logger.info(f"URL ajustada para usar pymysql: {database_url}")
        
        # Para MySQL no Render, substitui localhost pelo nome do serviço
        if "mysql" in database_url and "@localhost" in database_url:
            database_url = database_url.replace("@localhost", "@mysql")
            logger.info(f"URL ajustada para ambiente Render (localhost -> mysql): {database_url}")
        
        engine = create_engine(database_url)
        
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