FROM python:3.9-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
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
CMD ["sh", "-c", "if [ \"$SERVICE\" = \"api\" ]; then uvicorn aggregator_backend.main:app --host 0.0.0.0 --port $PORT; elif [ \"$SERVICE\" = \"worker\" ]; then celery -A aggregator_backend.tasks worker --loglevel=info; elif [ \"$SERVICE\" = \"beat\" ]; then celery -A aggregator_backend.tasks beat --loglevel=info; elif [ \"$SERVICE\" = \"flower\" ]; then celery -A aggregator_backend.tasks flower --port=$PORT; fi"]