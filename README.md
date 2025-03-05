# TrendPulse - Agregador de Tendências

O **TrendPulse** é um projeto que agrega conteúdo de diversas plataformas (YouTube e Reddit) e o disponibiliza por meio de uma API RESTful. A aplicação utiliza:

- **FastAPI** para criar a API
- **Celery** para processamento assíncrono e agendamento (usando Celery Beat)
- **Redis** como broker para o Celery
- **MySQL** para persistência dos dados
- **Flower** para monitoramento das tasks do Celery

Este projeto foi estruturado para rodar todos os serviços via Docker Compose, garantindo um ambiente isolado e fácil de configurar.

## Índice

- [Recursos e Funcionalidades](#recursos-e-funcionalidades)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Configuração](#instalação-e-configuração)
  - [Clonando o Repositório](#clonando-o-repositório)
  - [Configuração das Variáveis de Ambiente](#configuração-das-variáveis-de-ambiente)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Executando a Aplicação](#executando-a-aplicação)
  - [Modo Desenvolvimento](#modo-desenvolvimento)
  - [Modo Produção](#modo-produção)
- [API Endpoints](#api-endpoints)
- [Monitoramento com Flower](#monitoramento-com-flower)
- [Troubleshooting](#troubleshooting)
- [Contribuições](#contribuições)
- [Licença](#licença)
- [Deploy no Render.com](#deploy-no-rendercom)

## Recursos e Funcionalidades

- **Agregação de Conteúdo:** Busca dados de tendências do YouTube e Reddit
- **Persistência:** Armazena os resultados em um banco MySQL
- **Agendamento:** Atualiza os dados periodicamente usando Celery Beat:
  - **YouTube:** Atualiza a cada 3 horas
  - **Reddit:** Atualiza a cada 2 horas
- **API REST:** Disponibiliza endpoints para consulta dos dados agregados
- **Monitoramento:** Utiliza Flower para acompanhar as tasks do Celery
- **Categorização:** Classifica automaticamente as tendências em categorias
- **Deduplicação:** Evita duplicatas usando identificadores únicos por plataforma
- **URLs Diretas:** Armazena e disponibiliza URLs diretas para as tendências

## Pré-requisitos

- Docker e Docker Compose
- Chaves de API para:
  - YouTube Data API v3
  - Reddit (Client ID e Secret)

## Instalação e Configuração

### Clonando o Repositório

```bash
git clone https://github.com/<username>/trendpulse.git
cd trendpulse
```

### Configuração das Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```dotenv
# Credenciais da API do YouTube
YOUTUBE_API_KEY=your_youtube_api_key

# Credenciais da API do Reddit (fluxo de Script App)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_SECRET=your_reddit_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password

# Configuração do Banco de Dados
DATABASE_URL=sqlite:///data/aggregator.db

# Ambiente (development/production)
ENVIRONMENT=development

# URL do GitHub Pages (produção)
GITHUB_PAGES_URL=https://seu-usuario.github.io
```

## Estrutura do Projeto

```bash
trendpulse/
├── aggregator_backend/
│   ├── __init__.py
│   ├── main.py               # API FastAPI
│   ├── celery_app.py         # Configuração do Celery
│   ├── tasks.py              # Tasks de busca de dados
│   └── models.py             # Modelos do banco de dados
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Executando a Aplicação

Existem dois modos de execução: desenvolvimento e produção.

### Modo Desenvolvimento

No modo desenvolvimento, a API roda localmente (fora do Docker) para facilitar o debug, enquanto os serviços de suporte (MySQL, Redis, etc.) rodam via Docker.

1. Configure a variável de ambiente:
   ```bash
   # Windows
   set ENVIRONMENT=development
   
   # Linux/Mac
   export ENVIRONMENT=development
   ```

2. Inicie os serviços de suporte:
   ```bash
   docker-compose up -d mysql redis worker beat flower
   ```

3. Execute a API localmente:
   ```bash
   uvicorn aggregator_backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Modo Produção

No modo produção, todos os serviços, incluindo a API, rodam via Docker.

1. Configure a variável de ambiente (opcional, o padrão é "production"):
   ```bash
   # Windows
   set ENVIRONMENT=production
   
   # Linux/Mac
   export ENVIRONMENT=production
   ```

2. Inicie todos os serviços:
   ```bash
   docker-compose --profile production up -d
   ```

Isso iniciará:
- API FastAPI (porta 8000)
- MySQL (porta 3307)
- Redis (porta 6379)
- Worker do Celery
- Celery Beat
- Flower (porta 5555)

### Variáveis de Ambiente

Configure as seguintes variáveis no arquivo `.env`:

```dotenv
# Ambiente (development/production)
ENVIRONMENT=development

# Credenciais da API do YouTube
YOUTUBE_API_KEY=your_youtube_api_key

# Credenciais da API do Reddit
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_SECRET=your_reddit_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password

# URL do GitHub Pages (produção)
GITHUB_PAGES_URL=https://seu-usuario.github.io
```

## API Endpoints

### GET `/api/trends`

Retorna as tendências com opções de filtro.

**Parâmetros:**
- `platform`: Filtrar por plataforma (youtube, reddit)
- `category`: Filtrar por categoria
- `limit`: Número máximo de resultados (padrão: 1000)
- `skip`: Número de resultados a pular (paginação)

**Exemplo de resposta:**
```json
[
  {
    "id": 1,
    "title": "Título da Tendência",
    "description": "Descrição detalhada",
    "platform": "youtube",
    "category": "tecnologia",
    "author": "Canal Tech",
    "views": "1.5M",
    "likes": 150000,
    "comments": 5000,
    "timeAgo": "2 horas",
    "tags": ["tech", "tutorial"],
    "thumbnail": "https://...",
    "url": "https://youtube.com/watch?v=..."
  }
]
```

### POST `/api/fetch-trends`

Dispara manualmente a busca de tendências.

### GET `/api/categories`

Lista todas as categorias disponíveis e quantidade de tendências em cada uma.

### GET `/api/platforms`

Lista todas as plataformas disponíveis e quantidade de tendências em cada uma.

### GET `/api/status`

Retorna estatísticas gerais do sistema.

## Monitoramento com Flower

Acesse o dashboard do Flower em `http://localhost:5555` para monitorar:
- Tasks em execução
- Tasks agendadas
- Histórico de execuções
- Estado dos workers

## Troubleshooting

### Problemas Comuns

1. **Erro de Conexão com MySQL:**
   - Verifique se o container do MySQL está rodando: `docker-compose ps`
   - Verifique os logs: `docker-compose logs mysql`

2. **Tasks Não Executando:**
   - Verifique os logs do worker: `docker-compose logs worker`
   - Verifique se o Redis está acessível: `docker-compose logs redis`

3. **Erros de API:**
   - Verifique se as credenciais no `.env` estão corretas
   - Verifique os limites de quota das APIs

4. **Limpeza Total:**
   Para reiniciar do zero:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

## Deploy no Render.com

Para fazer o deploy da aplicação no Render.com:

1. Crie uma conta no [Render.com](https://render.com) e conecte seu repositório do GitHub.

2. No Dashboard do Render, clique em "New" e selecione "Blueprint".

3. Selecione o repositório onde está o código da aplicação.

4. O Render detectará automaticamente o arquivo `render.yaml` e criará todos os serviços necessários:
   - API FastAPI (Web Service)
   - Worker do Celery
   - Celery Beat
   - Redis
   - MySQL Database

5. Configure as variáveis de ambiente secretas:
   - `YOUTUBE_API_KEY`
   - `REDDIT_CLIENT_ID`
   - `REDDIT_SECRET`
   - `REDDIT_USERNAME`
   - `REDDIT_PASSWORD`
   - `GITHUB_PAGES_URL`

6. Clique em "Apply" para iniciar o deploy.

### Troubleshooting no Render

Se encontrar problemas durante o deploy no Render, verifique:

1. **Erro de conexão com o MySQL**:
   - Verifique se o serviço MySQL está em execução no dashboard do Render
   - Verifique se a string de conexão está correta (deve usar `mysql+pymysql://`)
   - O script `check_db.py` tentará se conectar várias vezes e mostrará logs detalhados

2. **Erro de porta**:
   - O Render exige que a aplicação use a porta definida na variável de ambiente `PORT`
   - Nosso `render.yaml` já está configurado para usar `--port $PORT`

3. **Serviços não iniciam**:
   - Verifique os logs de cada serviço no dashboard do Render
   - Pode ser necessário reiniciar manualmente os serviços após o primeiro deploy

4. **Problemas de CORS**:
   - Verifique se a variável `GITHUB_PAGES_URL` está configurada corretamente
   - Em produção, apenas requisições desse domínio serão aceitas

### Observações Importantes

- O plano gratuito do Render tem algumas limitações:
  - Os serviços "adormecem" após 15 minutos de inatividade
  - O banco MySQL tem limite de 1GB de armazenamento
  - O Redis tem limite de memória de 25MB
  - Há limites de banda e CPU

- Para o frontend, atualize a URL da API no seu código para apontar para a URL do Render:
  ```javascript
  const API_URL = process.env.NODE_ENV === 'production'
    ? 'https://trendpulse-api.onrender.com'
    : 'http://localhost:8000';
  ```

- Os logs de cada serviço podem ser visualizados no dashboard do Render.

- O primeiro deploy pode levar alguns minutos, pois o Render precisa construir a imagem Docker.

