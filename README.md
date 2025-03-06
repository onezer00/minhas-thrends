# TrendPulse - Agregador de Tendências

[![Tests](https://github.com/onezer00/minhas-thrends/actions/workflows/test.yml/badge.svg)](https://github.com/onezer00/minhas-thrends/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/onezer00/minhas-thrends/branch/main/graph/badge.svg)](https://codecov.io/gh/onezer00/minhas-thrends)
[![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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
- [Testes Automatizados](#testes-automatizados)
  - [Executando Testes](#executando-testes)
  - [Integração Contínua](#integração-contínua)
  - [Pré-commit](#pré-commit)
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

# Configuração do Banco de Dados (desenvolvimento)
DATABASE_URL=mysql+pymysql://root:root@localhost:3307/trendpulse

# Ambiente (development/production)
ENVIRONMENT=development

# URL do GitHub Pages (produção)
GITHUB_PAGES_URL=https://seu-usuario.github.io
```

### Configuração de Banco de Dados

O projeto está configurado para usar diferentes bancos de dados dependendo do ambiente:

#### Ambiente de Desenvolvimento
- **MySQL**: Usado localmente durante o desenvolvimento
- String de conexão: `mysql+pymysql://root:root@mysql:3306/trendpulse` (dentro do Docker)
- String de conexão: `mysql+pymysql://root:root@localhost:3307/trendpulse` (fora do Docker)

#### Ambiente de Produção (Render)
- **PostgreSQL**: Usado em produção no Render
- String de conexão: Fornecida automaticamente pelo Render
- O sistema detecta automaticamente o ambiente e ajusta a conexão

#### Fallback
- **SQLite**: Usado como fallback em caso de falha na conexão com MySQL/PostgreSQL
- Localização: Diretório temporário do sistema ou em memória como último recurso

### Dependências de Banco de Dados

O projeto inclui drivers para ambos os bancos de dados:
- `pymysql` e `mysqlclient` para MySQL
- `psycopg2-binary` para PostgreSQL

O sistema detecta automaticamente qual driver usar com base na string de conexão.

## Estrutura do Projeto

```bash
trendpulse/
├── app/
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
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

## Testes Automatizados

O TrendPulse possui uma suíte completa de testes automatizados, incluindo testes unitários e de integração. Os testes são executados automaticamente a cada commit e antes do deploy, garantindo a qualidade do código.

### Executando Testes

Você pode executar os testes de várias maneiras:

#### Usando o script pre_deploy_tests.sh

```bash
# Executar todos os testes e gerar relatório de cobertura
bash ./pre_deploy_tests.sh
```

#### Usando pytest diretamente

```bash
# Executar todos os testes
pytest

# Executar testes com marcador específico
pytest -m unit
pytest -m integration

# Gerar relatório de cobertura
pytest --cov=app tests/
```

### Integração Contínua

O projeto utiliza GitHub Actions para executar os testes automaticamente a cada push ou pull request. O fluxo de trabalho está configurado em `.github/workflows/test.yml` e inclui:

1. Execução de todos os testes
2. Geração de relatório de cobertura
3. Upload do relatório para o Codecov
4. Notificação para o Render para deploy (apenas na branch principal)

### Cobertura de Código

A cobertura de código é monitorada pelo [Codecov](https://codecov.io/gh/onezer00/minhas-thrends). O badge no topo do README mostra a cobertura atual. O objetivo é manter a cobertura acima de 60%.

Você pode ver o relatório detalhado de cobertura clicando no badge do Codecov ou acessando diretamente o [dashboard do Codecov](https://codecov.io/gh/onezer00/minhas-thrends).

### Pré-commit

O projeto usa pre-commit para verificar o código antes de cada commit. Para configurar:

```bash
# Instalar e configurar o pre-commit
python setup_pre_commit.py

# Executar manualmente em todos os arquivos
pre-commit run --all-files
```

Os hooks do pre-commit verificam:
- Formatação do código (black)
- Ordenação de imports (isort)
- Estilo de código (flake8)
- Execução de testes unitários

## Troubleshooting

### Problemas Comuns

1. **Erro de Conexão com Banco de Dados:**
   - Verifique se o container do banco de dados está rodando: `docker-compose ps`
   - Verifique os logs: `docker-compose logs mysql` (desenvolvimento) ou `docker-compose logs postgres` (produção)
   - Execute o script de diagnóstico: `python -m app.check_db`
   - Em produção (Render), verifique se o serviço PostgreSQL está ativo

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

5. **Problemas com o Banco de Dados:**
   - O sistema detecta automaticamente o ambiente e usa o driver apropriado:
     - MySQL com pymysql em desenvolvimento
     - PostgreSQL com psycopg2 em produção
   - Em caso de falha, o sistema tem um fallback automático para SQLite
   - Para diagnosticar problemas de conexão: `python -m app.check_db --max-attempts 5 --wait-time 10`

6. **Problemas com o Redis:**
   - O sistema tentará automaticamente ajustar a URL do Redis para usar o nome completo do serviço no Render
   - Você pode verificar a conexão manualmente com: `python -m app.check_db --skip-db`

7. **Problemas de CORS:**
   - Verifique se a variável `GITHUB_PAGES_URL` está configurada corretamente
   - Em produção, apenas requisições desse domínio serão aceitas

8. **Diagnóstico avançado:**
   - Adicione a variável de ambiente `PYTHONUNBUFFERED=1` para ver logs em tempo real
   - Execute o script de diagnóstico com mais tentativas: `python -m app.check_db --max-attempts 10 --wait-time 15`
   - Verifique os logs do sistema para erros específicos

## Deploy no Render.com

Para fazer o deploy da aplicação no Render.com:

1. Crie uma conta no [Render.com](https://render.com) e conecte seu repositório do GitHub.

2. **Crie um banco de dados PostgreSQL**:
   - No Dashboard do Render, clique em "New" e selecione "PostgreSQL"
   - Configure o banco de dados:
     - Nome: `trendpulse`
     - Database: deixe em branco para gerar automaticamente
     - User: deixe em branco para gerar automaticamente
     - Região: escolha a mais próxima de você
     - Versão: 15 ou 16
     - Plano: Free
   - Clique em "Create Database"
   - **Importante**: Anote a string de conexão fornecida após a criação

3. No Dashboard do Render, clique em "New" e selecione "Blueprint".

4. Selecione o repositório onde está o código da aplicação.

5. O Render detectará automaticamente o arquivo `render.yaml` e criará os seguintes serviços:
   - API FastAPI (Web Service)
   - Flower Dashboard (Web Service)
   - Worker do Celery
   - Celery Beat
   - Redis

6. Configure as variáveis de ambiente secretas em cada serviço:
   - `DATABASE_URL`: Cole a string de conexão do PostgreSQL que você anotou
   - `YOUTUBE_API_KEY`
   - `REDDIT_CLIENT_ID`
   - `REDDIT_SECRET`
   - `REDDIT_USERNAME`
   - `REDDIT_PASSWORD`
   - `GITHUB_PAGES_URL`
   - `FLOWER_BASIC_AUTH` (opcional, formato: "usuario:senha")
   - `ENVIRONMENT=production` (importante para usar PostgreSQL)

7. Clique em "Apply" para iniciar o deploy.

### Banco de Dados no Render

O projeto está configurado para usar PostgreSQL em produção no Render:

1. Você precisa criar o banco de dados PostgreSQL manualmente antes de criar os outros serviços
2. O sistema detecta automaticamente o ambiente de produção e configura o driver psycopg2
3. A string de conexão deve ser configurada manualmente em cada serviço
4. Em caso de falha, o sistema tem um fallback para SQLite

### Acessando o Flower no Render

O Flower estará disponível em uma URL separada fornecida pelo Render. Para acessá-lo:

1. No dashboard do Render, localize o serviço `trendpulse-flower`
2. Clique no serviço para ver os detalhes
3. Use a URL fornecida pelo Render, que será algo como `https://trendpulse-flower.onrender.com`
   - **Importante**: Não é necessário adicionar `/flower` ao final da URL
4. Se você configurou a variável `FLOWER_BASIC_AUTH`, será solicitado um nome de usuário e senha

O Flower no Render permite que você:
- Monitore as tasks em execução
- Veja o histórico de execuções
- Cancele ou reinicie tasks
- Visualize estatísticas de desempenho

> **Nota**: O Flower no plano gratuito do Render também entrará em modo de "sleep" após 15 minutos de inatividade, assim como os outros serviços.

### Troubleshooting no Render

Se encontrar problemas durante o deploy no Render, verifique:

1. **Erro de conexão com o banco de dados**:
   - Verifique se o serviço PostgreSQL está em execução no dashboard do Render
   - O sistema detecta automaticamente o ambiente de produção e configura o driver psycopg2
   - O script `check_db.py` tentará se conectar várias vezes e mostrará logs detalhados
   - O sistema tem fallback automático para SQLite em caso de falha na conexão

2. **Erro de conexão com o Redis**:
   - Se encontrar erros como `'NoneType' object has no attribute 'push'` ou `Name or service not known`
   - O sistema tentará automaticamente ajustar a URL do Redis para usar o nome completo do serviço no Render
   - Você pode verificar a conexão manualmente com: `python -m app.check_db --skip-db`
   - Se o problema persistir, reinicie o serviço Redis no dashboard do Render

3. **Erro de porta**:
   - O Render exige que a aplicação use a porta definida na variável de ambiente `PORT`
   - Nosso `render.yaml` e `Procfile` já estão configurados para usar `--port $PORT`

4. **Serviços não iniciam**:
   - Verifique os logs de cada serviço no dashboard do Render
   - Pode ser necessário reiniciar manualmente os serviços após o primeiro deploy
   - Tente usar o `Procfile` em vez do `render.yaml` se continuar tendo problemas

5. **Problemas de CORS**:
   - Verifique se a variável `GITHUB_PAGES_URL` está configurada corretamente
   - Em produção, apenas requisições desse domínio serão aceitas

6. **Erro de permissão de arquivo**:
   - Se o SQLite for usado como fallback, ele agora usará o diretório temporário do sistema
   - Isso resolve problemas de permissão em ambientes como o Render

7. **Diagnóstico avançado**:
   - Adicione a variável de ambiente `PYTHONUNBUFFERED=1` para ver logs em tempo real
   - Execute o script de diagnóstico com mais tentativas: `python -m app.check_db --max-attempts 10 --wait-time 15`
   - Verifique os logs do sistema para erros específicos

8. **Problemas com Celery**:
   - Se as tarefas não estiverem sendo executadas, verifique a conexão com o Redis
   - O Celery precisa de uma conexão estável com o Redis para funcionar corretamente
   - Você pode monitorar as tarefas através do Flower: `https://trendpulse-flower.onrender.com/flower`

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

