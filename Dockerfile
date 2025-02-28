FROM python:3.10-slim

# Define o diretório de trabalho
WORKDIR /app

# Copia o arquivo de dependências e instala-as
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cria um diretório para armazenar o banco de dados (SQLite) ou outros dados persistentes
RUN mkdir -p /app/data

# Copia o código-fonte da aplicação
COPY aggregator_backend ./aggregator_backend

# Comando padrão (este comando pode ser sobrescrito no docker-compose para rodar worker, beat ou flower)
CMD ["uvicorn", "aggregator_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
