FROM python:3.9-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Cria um usuário não-root
RUN useradd -ms /bin/sh appuser

# Muda para o novo usuário
USER appuser

# Copia requirements primeiro para aproveitar o cache de camadas do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Configura as variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Comando de inicialização baseado em uma variável de ambiente
CMD ["sh", "-c", "if [ \"$SERVICE\" = \"api\" ]; then python -m app.check_db --max-attempts 10 --wait-time 10 && python -c 'from app.models import create_tables; create_tables()' && uvicorn app.main:app --host 0.0.0.0 --port $PORT; elif [ \"$SERVICE\" = \"worker\" ]; then python -m app.check_db --max-attempts 10 --wait-time 10 && python -m celery -A app.tasks worker --loglevel=info; elif [ \"$SERVICE\" = \"beat\" ]; then python -m app.check_db --max-attempts 10 --wait-time 10 && python -m celery -A app.tasks beat --loglevel=info; elif [ \"$SERVICE\" = \"flower\" ]; then python -m app.check_db --max-attempts 10 --wait-time 10 --skip-db && python -m celery -A app.tasks flower --port=$PORT; fi"]