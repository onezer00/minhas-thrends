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
- [API Endpoints](#api-endpoints)
- [Monitoramento com Flower](#monitoramento-com-flower)
- [Troubleshooting](#troubleshooting)
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

Para iniciar todos os serviços:

```bash
docker-compose up -d
```

Isso iniciará:
- MySQL (porta 3307)
- Redis (porta 6379)
- Worker do Celery
- Celery Beat
- Flower (porta 5555)

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

O projeto está configurado para deploy gratuito no Render.com. Siga os passos:

1. Crie uma conta no [Render.com](https://render.com)

2. Conecte seu repositório GitHub ao Render

3. Configure as variáveis de ambiente no Render:
   ```
   YOUTUBE_API_KEY=sua_chave_api_youtube
   REDDIT_CLIENT_ID=seu_client_id_reddit
   REDDIT_SECRET=seu_secret_reddit
   REDDIT_USERNAME=seu_usuario_reddit
   REDDIT_PASSWORD=sua_senha_reddit
   GITHUB_PAGES_URL=https://seu-usuario.github.io
   ```

4. Clique em "Deploy" e aguarde a conclusão

O Render irá automaticamente:
- Criar um banco MySQL gratuito
- Configurar um Redis gratuito
- Iniciar os serviços da API, Worker e Beat
- Configurar as URLs e variáveis de ambiente

### URLs do Serviço

Após o deploy, você terá acesso às seguintes URLs:
- API: `https://trendpulse-api.onrender.com`
- Flower Dashboard: `https://trendpulse-api.onrender.com/flower`

### Limitações do Plano Gratuito

- Banco MySQL: 
  - 256 MB de armazenamento
  - Backup automático diário
  - Conexões limitadas

- Redis:
  - 25 MB de memória
  - Sem persistência
  - Conexões limitadas

- Serviços:
  - Spin down após 15 minutos de inatividade
  - 512 MB de RAM por serviço
  - Banda limitada

### Configuração do Frontend

No seu projeto frontend (GitHub Pages), configure a URL da API:

```javascript
const API_URL = process.env.NODE_ENV === 'production'
  ? 'https://trendpulse-api.onrender.com'
  : 'http://localhost:8000';
```

