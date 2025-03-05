import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_environment_variables():
    """Verifica se todas as variáveis de ambiente necessárias estão configuradas."""
    required_vars = [
        'DATABASE_URL',
        'CELERY_BROKER_URL',
        'CELERY_RESULT_BACKEND',
        'YOUTUBE_API_KEY',
        'REDDIT_CLIENT_ID',
        'REDDIT_SECRET',
        'REDDIT_USERNAME',
        'REDDIT_PASSWORD'
    ]
    
    optional_vars = [
        'GITHUB_PAGES_URL',
        'FLOWER_BASIC_AUTH',
        'ENVIRONMENT'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
            logger.error(f"Variável de ambiente obrigatória não configurada: {var}")
    
    for var in optional_vars:
        if not os.environ.get(var):
            logger.warning(f"Variável de ambiente opcional não configurada: {var}")
    
    if missing_vars:
        logger.error(f"Faltam {len(missing_vars)} variáveis de ambiente obrigatórias!")
        return False
    
    logger.info("Todas as variáveis de ambiente obrigatórias estão configuradas!")
    return True

if __name__ == "__main__":
    check_environment_variables()