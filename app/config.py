import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (se existir)
load_dotenv()

# Configurações do Celery (broker e backend)
BROKER_URL = os.getenv("BROKER_URL", "redis://localhost:6379/0")
BACKEND_URL = os.getenv("BACKEND_URL", "redis://localhost:6379/0")

# Credenciais da API do Twitter
TWITTER_BEARER = os.getenv("TWITTER_BEARER", "")

# Credenciais da API do YouTube
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Credenciais da API do Reddit (para fluxo de Script App)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_SECRET = os.getenv("REDDIT_SECRET", "")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")

# Configuração do Banco de Dados
# Se a variável DATABASE_URL não estiver definida, utiliza SQLite no diretório /app/data/aggregator.db
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/aggregator.db")
