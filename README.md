# Minhas Thrends Documentation

O **Minhas Thrends** é um projeto que agrega conteúdo de diversas plataformas (Twitter, YouTube e Reddit) e o disponibiliza por meio de uma API RESTful. A aplicação utiliza:

- **FastAPI** para criar a API.
- **Celery** para processamento assíncrono e agendamento (usando Celery Beat).
- **Redis** como broker para o Celery.
- **SQLite** para persistência dos dados (com possibilidade de migração para PostgreSQL).
- **Flower** para monitoramento das tasks do Celery.

Este projeto foi estruturado para rodar os serviços de background (Worker, Beat, Flower e Redis) via Docker, enquanto a API pode ser executada localmente para facilitar o debug.

## Índice

- [Recursos e Funcionalidades](#recursos-e-funcionalidades)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Configuração](#instalação-e-configuração)
  - [Clonando o Repositório](#clonando-o-repositório)
  - [Ambiente Virtual e Dependências](#ambiente-virtual-e-dependências)
  - [Configuração das Variáveis de Ambiente](#configuração-das-variáveis-de-ambiente)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Executando a Aplicação](#executando-a-aplicação)
  - [Rodando a API Localmente](#rodando-a-api-localmente)
  - [Rodando os Serviços de Background com Docker Compose](#rodando-os-serviços-de-background-com-docker-compose)
- [API Endpoints](#api-endpoints)
- [Agendamento de Tarefas com Celery](#agendamento-de-tarefas-com-celery)
- [Monitoramento com Flower](#monitoramento-com-flower)
- [Troubleshooting](#troubleshooting)
- [Contribuições](#contribuições)
- [Licença](#licença)

## Recursos e Funcionalidades

- **Agregação de Conteúdo:** Busca dados de trending topics de Twitter, YouTube e Reddit.
- **Persistência:** Armazena os resultados em um banco de dados.
- **Agendamento:** Atualiza os dados periodicamente usando Celery Beat:
  - **Twitter:** Atualiza a cada 8 horas.
  - **YouTube e Reddit:** Atualizam a cada 1 hora.
- **API REST:** Disponibiliza um endpoint para consulta dos dados agregados.
- **Monitoramento:** Utiliza Flower para acompanhar as tasks do Celery.

## Pré-requisitos

- Python 3.10+
- Docker e Docker Compose (para serviços de background)
- Redis (incluso via Docker)
- Contas e chaves de API para Twitter, YouTube e Reddit.

## Instalação e Configuração

### Clonando o Repositório

```bash
git clone https://github.com/<username>/aggregator-backend.git
cd aggregator-backend
```
## Ambiente Virtual e Dependências
Crie e ative um ambiente virtual:

```bash
python -m venv venv
source venv/bin/activate   # No Windows: venv\Scripts\activate
```
Instale as dependências:

```bash
pip install -r requirements.txt
```
### Configuração das Variáveis de Ambiente
Crie um arquivo ``.env`` na raiz do projeto com as seguintes variáveis (ajuste conforme necessário):

```dotenv
# Broker e Backend para o Celery
BROKER_URL=redis://localhost:6379/0
BACKEND_URL=redis://localhost:6379/0

# Credenciais da API do Twitter
TWITTER_BEARER=your_twitter_bearer_token

# Credenciais da API do YouTube
YOUTUBE_API_KEY=your_youtube_api_key

# Credenciais da API do Reddit (fluxo de Script App)
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_SECRET=your_reddit_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password

# Configuração do Banco de Dados
DATABASE_URL=sqlite:///data/aggregator.db

```

## Estrutura do Projeto
```bash
aggregator-backend/
├── aggregator_backend/
│   ├── __init__.py
│   ├── main.py               # Entrypoint da API FastAPI
│   ├── celery_app.py         # Configuração do Celery e agendamento das tasks
│   ├── tasks.py              # Definição das tasks para buscar dados
│   ├── models.py             # Modelos e configuração do banco de dados
│   └── config.py             # Carrega configurações e variáveis de ambiente
├── requirements.txt          # Dependências do Python
├── Dockerfile                # Definição da imagem Docker
├── docker-compose.yml        # Configuração dos serviços via Docker Compose
├── .gitignore                # Arquivo para ignorar arquivos indesejados no Git
└── README.md                 # Documentação deste projeto

```
## Executando a Aplicação
### Rodando a API Localmente
Para executar a API FastAPI fora do Docker (ideal para debug), use:

```bash
uvicorn aggregator_backend.main:app --host 0.0.0.0 --port 8000
```
A API ficará disponível em http://localhost:8000.

### Rodando os Serviços de Background com Docker Compose
Para rodar os serviços de background (Celery Worker, Beat, Flower e Redis) via Docker, use o seguinte comando:

```bash
docker-compose build
docker-compose up -d
```

Os serviços iniciados serão:

- **redis**: Broker para o Celery.
- **worker**: Processa as tasks do Celery.
- **beat**: Agenda as tasks conforme configurado.
- **flower**: Interface de monitoramento do Celery, acessível em http://localhost:5555.
## API Endpoints
### GET ``/trends``
Retorna os registros de conteúdo agregado, permitindo filtrar por plataforma e keyword.

**Exemplo de requisição**:

```bash
curl "http://localhost:8000/trends?keyword=python"
curl "http://localhost:8000/trends?platform=youtube"
```
**Exemplo de resposta**:

```json
[
  {
    "id": 1,
    "platform": "youtube",
    "keyword": "python",
    "title": "Learn Python in 10 Minutes (for Beginners)",
    "content": { "snippet": { ... } },
    "created_at": "2025-02-28T13:02:18.941411"
  },
  ...
]
```
## Agendamento de Tarefas com Celery
O arquivo ``celery_app.py`` configura o Celery e define o agendamento das tasks:

- Twitter: A task ``fetch_twitter_data`` é executada a cada 8 horas.
- YouTube e Reddit: Suas tasks são executadas a cada 1 hora.
## Monitoramento com Flower
Flower é usado para monitorar as tasks do Celery. Após iniciar os serviços com Docker Compose, acesse a interface de Flower em http://localhost:5555.

## Troubleshooting
- **Rate Limits**: Se receber um erro 429 (Too Many Requests), verifique os cabeçalhos da resposta da API e ajuste a frequência das chamadas.
- **Banco de Dados**: Assegure que os contêineres compartilhem o mesmo volume para o SQLite ou considere usar um banco de dados centralizado como o PostgreSQL.
- **Variáveis de Ambiente**: Certifique-se de que todas as variáveis de ambiente estão corretamente definidas no arquivo ``.env`` e passadas aos contêineres.
- **Debug**: Para depurar as tasks, considere chamar as funções diretamente fora do contexto do Celery para facilitar o uso de breakpoints.
## Contribuições
Contribuições são bem-vindas! Se você encontrar bugs ou tiver sugestões de melhorias, por favor, abra uma issue ou envie um pull request.

## Licença
Este projeto é licenciado sob a MIT License. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

