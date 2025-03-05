import os
import sys
import time
import logging
from sqlalchemy import create_engine, text

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

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
        
        engine = create_engine(database_url)
        
        # Tenta conectar e executar uma consulta simples
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info(f"Conexão bem-sucedida! Resultado: {result.fetchone()}")
            
            # Verifica informações do banco de dados
            db_info = connection.execute(text("SELECT VERSION()"))
            logger.info(f"Versão do banco de dados: {db_info.fetchone()}")
            
        return True
    
    except Exception as e:
        logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return False

if __name__ == "__main__":
    # Tenta conectar várias vezes (útil para esperar o banco inicializar)
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Tentativa {attempt} de {max_attempts}...")
        
        if check_database_connection():
            logger.info("Conexão com o banco de dados estabelecida com sucesso!")
            sys.exit(0)
        
        if attempt < max_attempts:
            wait_time = 5  # segundos
            logger.info(f"Aguardando {wait_time} segundos antes da próxima tentativa...")
            time.sleep(wait_time)
    
    logger.error(f"Falha ao conectar ao banco de dados após {max_attempts} tentativas.")
    sys.exit(1) 