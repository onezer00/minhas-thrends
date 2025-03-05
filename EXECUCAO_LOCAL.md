# Executando o TrendPulse Localmente

Este guia fornece instruções detalhadas sobre como executar o TrendPulse em seu ambiente local de desenvolvimento.

## Pré-requisitos

Antes de começar, certifique-se de ter instalado:

- [Docker](https://www.docker.com/products/docker-desktop) e [Docker Compose](https://docs.docker.com/compose/install/)
- [Python 3.9+](https://www.python.org/downloads/) (caso queira executar a API fora do Docker)
- [Git](https://git-scm.com/downloads) para clonar o repositório

## Configuração Inicial

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/trendpulse.git
cd trendpulse
```

### 2. Configure as Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```dotenv
# Ambiente (development/production)
ENVIRONMENT=development

# Credenciais da API do YouTube
YOUTUBE_API_KEY=sua_chave_api_youtube

# Credenciais da API do Reddit
REDDIT_CLIENT_ID=seu_client_id_reddit
REDDIT_SECRET=seu_secret_reddit
REDDIT_USERNAME=seu_usuario_reddit
REDDIT_PASSWORD=sua_senha_reddit

# URL do GitHub Pages (opcional para desenvolvimento)
GITHUB_PAGES_URL=https://seu-usuario.github.io
```

## Executando com Docker Compose

O método recomendado para executar o TrendPulse localmente é usando Docker Compose, que iniciará todos os serviços necessários em contêineres isolados.

### Método 1: Todos os Serviços via Docker

Este método inicia todos os serviços, incluindo a API, usando Docker:

```bash
# Defina o ambiente como development
export ENVIRONMENT=development  # ou set ENVIRONMENT=development no Windows

# Inicie todos os serviços
docker-compose up -d
```

Isso iniciará:
- API FastAPI (porta 8000)
- MySQL (porta 3307)
- Redis (porta 6379)
- Worker do Celery
- Celery Beat
- Flower (porta 5555)

### Método 2: API Local + Serviços de Suporte via Docker

Este método é útil para desenvolvimento, pois permite executar a API localmente (fora do Docker) para facilitar o debug, enquanto os serviços de suporte (MySQL, Redis, etc.) rodam via Docker:

```bash
# Defina o ambiente como development
export ENVIRONMENT=development  # ou set ENVIRONMENT=development no Windows

# Inicie os serviços de suporte
docker-compose up -d mysql redis worker beat flower

# Em outro terminal, instale as dependências e execute a API localmente
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Verificando a Instalação

Após iniciar os serviços, você pode verificar se tudo está funcionando corretamente:

### 1. Verifique o Status da API

Acesse http://localhost:8000/api/status no navegador ou use:

```bash
curl http://localhost:8000/api/status
```

Você deve ver uma resposta JSON indicando que a API está conectada ao Redis e ao banco de dados:

```json
{
  "status": "ok",
  "redis": "connected",
  "database": "connected",
  "timestamp": "2025-03-05T20:39:42.948396",
  "cached": false
}
```

### 2. Acesse o Dashboard do Flower

Abra http://localhost:5555 no navegador para acessar o dashboard do Flower, que permite monitorar as tarefas do Celery.

### 3. Teste os Endpoints da API

- Lista de tendências: http://localhost:8000/api/trends
- Categorias disponíveis: http://localhost:8000/api/categories
- Plataformas disponíveis: http://localhost:8000/api/platforms

## Solução de Problemas

### Problema com o Redis

Se o Redis não iniciar corretamente, pode ser devido a um problema com o arquivo de persistência. Tente:

```bash
docker-compose down -v  # Remove os volumes
docker-compose up -d    # Inicia novamente
```

### Problema com o Flower

Se o Flower não estiver acessível, verifique se as variáveis de ambiente estão configuradas corretamente no arquivo `docker-compose.yml`:

```yaml
flower:
  environment:
    - DATABASE_URL=mysql+pymysql://root:root@mysql:3306/trendpulse
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
    - FLOWER_DB=/tmp/flower
```

### Problema com o Worker ou Beat

Se as tarefas não estiverem sendo executadas, verifique os logs:

```bash
docker-compose logs worker
docker-compose logs beat
```

### Reiniciando do Zero

Para reiniciar completamente a aplicação:

```bash
docker-compose down -v  # Para todos os serviços e remove volumes
docker-compose up -d    # Inicia novamente
```

## Desenvolvimento

Durante o desenvolvimento, você pode querer:

1. **Visualizar logs em tempo real**:
   ```bash
   docker-compose logs -f api  # ou worker, beat, flower, etc.
   ```

2. **Executar tarefas manualmente**:
   ```bash
   curl -X POST http://localhost:8000/api/fetch-trends
   ```

3. **Acessar o banco de dados**:
   ```bash
   docker exec -it trendpulse_mysql mysql -uroot -proot trendpulse
   ```

4. **Verificar o Redis**:
   ```bash
   docker exec -it trendpulse_redis redis-cli
   ```

## Próximos Passos

Após configurar o ambiente local, você pode:

1. Explorar a API através da documentação Swagger: http://localhost:8000/docs
2. Desenvolver novos recursos
3. Conectar um frontend ao backend
4. Configurar o deploy para produção seguindo as instruções no README principal

## Compatibilidade entre Ambientes de Desenvolvimento e Produção

O TrendPulse foi projetado para funcionar de forma consistente tanto em ambiente de desenvolvimento local quanto em produção (Render). As seguintes características garantem essa compatibilidade:

### Detecção Automática de Ambiente

O sistema detecta automaticamente o ambiente através da variável `ENVIRONMENT`:

```python
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_DEVELOPMENT = ENVIRONMENT.lower() == "development"
```

### Configuração de Banco de Dados Adaptativa

- **Desenvolvimento**: Usa MySQL via Docker
- **Produção**: Usa PostgreSQL no Render
- **Fallback**: SQLite em caso de falha na conexão

### Configuração CORS Inteligente

Em ambiente de desenvolvimento, origens locais são automaticamente permitidas:

```python
# Em desenvolvimento, adiciona origens locais
if IS_DEVELOPMENT:
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])
```

### Otimizações para Redis

As configurações de conexão ao Redis foram otimizadas para funcionar em ambos os ambientes:

- Limites de conexão reduzidos para evitar sobrecarga
- Detecção automática da URL do Redis
- Verificação de conexão com fallback

### Configuração do Flower

O Flower foi configurado para usar menos recursos e funcionar em ambos os ambientes:

```yaml
flower:
  environment:
    - DATABASE_URL=mysql+pymysql://root:root@mysql:3306/trendpulse
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
    - FLOWER_DB=/tmp/flower
```

### Dockerfile Flexível

O Dockerfile foi projetado para suportar diferentes tipos de serviços através da variável `SERVICE`:

```dockerfile
CMD ["sh", "-c", "if [ \"$SERVICE\" = \"api\" ]; then ... elif [ \"$SERVICE\" = \"worker\" ]; then ... fi"]
```

Isso permite que o mesmo Dockerfile seja usado para todos os serviços, tanto em desenvolvimento quanto em produção.

## Alterações Recentes para Melhorar a Estabilidade

Recentemente, fizemos várias alterações para melhorar a estabilidade da aplicação, especialmente em relação ao Redis e ao Flower:

### 1. Otimização das Conexões Redis

Reduzimos os limites de conexão no arquivo `app/celery_app.py`:

```python
app.conf.broker_pool_limit = 5  # Reduzido de 20
app.conf.redis_max_connections = 10  # Reduzido de 40
```

Isso evita que o sistema exceda o limite de conexões do Redis, especialmente em ambientes com recursos limitados.

### 2. Configuração do Flower

Adicionamos variáveis de ambiente específicas para o Flower no `docker-compose.yml`:

```yaml
flower:
  environment:
    - DATABASE_URL=mysql+pymysql://root:root@mysql:3306/trendpulse
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
    - FLOWER_DB=/tmp/flower
```

E modificamos o comando para incluir o parâmetro `--db`:

```yaml
command: celery -A app.tasks flower --port=5555 --db=/tmp/flower
```

### 3. Verificação de Conexão com Verbose Reduzido

Adicionamos o parâmetro `verbose=False` na verificação de conexão do Redis no endpoint `/api/status`:

```python
redis_ok = check_redis_connection(verbose=False)
```

Isso reduz a quantidade de logs gerados durante as verificações de rotina.

### 4. Diretório Temporário para o Celery Beat

Configuramos um diretório temporário com permissões adequadas para o arquivo de agendamento do Celery Beat:

```dockerfile
RUN mkdir -p /tmp/celerybeat && \
    chown -R appuser:appuser /tmp/celerybeat && \
    chmod -R 755 /tmp/celerybeat
```

Isso resolve problemas de permissão que poderiam ocorrer com o arquivo `celerybeat-schedule`.

### 5. Solução para Problemas de Persistência do Redis

Se você encontrar problemas com o Redis devido a arquivos de persistência corrompidos, a solução é remover os volumes e reiniciar:

```bash
docker-compose down -v  # Remove os volumes
docker-compose up -d    # Inicia novamente
```

Estas alterações garantem que a aplicação funcione de forma estável tanto em ambiente de desenvolvimento quanto em produção. 

## Monitoramento da Aplicação

Para garantir que sua aplicação TrendPulse esteja funcionando corretamente, você pode utilizar várias ferramentas e métodos de monitoramento:

### 1. Monitoramento via Flower

O Flower é uma ferramenta web para monitoramento e administração de tarefas Celery. Acesse-o em:

```
http://localhost:5555
```

No Flower você pode:
- Visualizar tarefas ativas, pendentes, concluídas e com falha
- Ver estatísticas de desempenho das tarefas
- Monitorar workers ativos
- Inspecionar detalhes de tarefas específicas
- Cancelar tarefas em execução

### 2. Logs dos Containers

Para visualizar logs em tempo real de cada serviço:

```bash
# Logs da API
docker logs -f trendpulse_api

# Logs do Worker
docker logs -f trendpulse_worker

# Logs do Beat
docker logs -f trendpulse_beat

# Logs do Flower
docker logs -f trendpulse_flower

# Logs do Redis
docker logs -f trendpulse_redis

# Logs do MySQL
docker logs -f trendpulse_mysql
```

Adicione a flag `--tail 100` para ver apenas as últimas 100 linhas:

```bash
docker logs -f --tail 100 trendpulse_worker
```

### 3. Endpoint de Status da API

O endpoint `/api/status` fornece informações sobre o estado atual da aplicação:

```bash
curl http://localhost:8000/api/status
```

A resposta inclui:
- Status da conexão com o banco de dados
- Status da conexão com o Redis
- Versão da aplicação
- Ambiente de execução

### 4. Monitoramento de Recursos

Para monitorar o uso de recursos dos containers Docker:

```bash
docker stats
```

Este comando mostra o uso de CPU, memória e rede de cada container em tempo real.

### 5. Verificação de Tarefas Agendadas

Para verificar se as tarefas agendadas estão sendo executadas corretamente:

```bash
# Verificar logs do Beat para tarefas agendadas
docker logs -f trendpulse_beat

# Verificar logs do Worker para execução de tarefas
docker logs -f trendpulse_worker | grep "Task app.tasks"
```

### 6. Acesso Direto ao Redis

Para inspecionar diretamente o Redis:

```bash
docker exec -it trendpulse_redis redis-cli
```

Comandos úteis no Redis CLI:
```
# Listar todas as chaves
KEYS *

# Ver informações sobre o servidor
INFO

# Ver estatísticas de memória
INFO memory

# Ver clientes conectados
CLIENT LIST
```

### 7. Acesso ao Banco de Dados

Para acessar diretamente o MySQL:

```bash
docker exec -it trendpulse_mysql mysql -u root -proot trendpulse
```

Consultas úteis:
```sql
-- Ver todas as tabelas
SHOW TABLES;

-- Ver tendências recentes
SELECT * FROM trends ORDER BY created_at DESC LIMIT 10;

-- Ver contagem de tendências por fonte
SELECT source, COUNT(*) FROM trends GROUP BY source;
```

Estas ferramentas de monitoramento ajudarão você a identificar e resolver problemas rapidamente, garantindo que sua aplicação TrendPulse funcione de maneira eficiente. 

## Atualizando a Aplicação

Quando houver mudanças no código ou na configuração da aplicação, siga estes passos para atualizar sua instância local:

### 1. Atualização do Código

Se você estiver trabalhando com um repositório Git:

```bash
# Obter as últimas alterações
git pull origin main

# Se você tiver alterações locais que deseja preservar
git stash
git pull origin main
git stash pop
```

### 2. Reconstrução dos Containers

Após atualizar o código, reconstrua os containers para aplicar as mudanças:

```bash
# Parar os containers atuais
docker-compose down

# Reconstruir e iniciar os containers
docker-compose up -d --build
```

Use a flag `--build` para garantir que as imagens sejam reconstruídas com o código atualizado.

### 3. Atualizações de Dependências

Se houver alterações no arquivo `requirements.txt`:

```bash
# Reconstruir apenas os serviços afetados
docker-compose build api worker beat flower
docker-compose up -d
```

### 4. Migrações de Banco de Dados

Se houver alterações no esquema do banco de dados:

```bash
# Executar migrações manualmente (se necessário)
docker-compose exec api alembic upgrade head
```

### 5. Verificação Pós-Atualização

Após a atualização, verifique se tudo está funcionando corretamente:

```bash
# Verificar status da API
curl http://localhost:8000/api/status

# Verificar logs para erros
docker-compose logs --tail=100
```

### 6. Rollback em Caso de Problemas

Se encontrar problemas após a atualização:

```bash
# Reverter para a versão anterior do código
git checkout <commit-anterior>

# Reconstruir os containers
docker-compose down
docker-compose up -d --build
```

### 7. Limpeza Periódica

Periodicamente, é recomendável limpar recursos não utilizados:

```bash
# Remover containers parados
docker container prune -f

# Remover imagens não utilizadas
docker image prune -f

# Remover volumes não utilizados (cuidado: pode apagar dados)
docker volume prune -f
```

### 8. Backup Antes de Atualizações Importantes

Antes de atualizações significativas, faça backup do banco de dados:

```bash
# Backup do MySQL
docker exec trendpulse_mysql sh -c 'exec mysqldump -u root -proot trendpulse' > backup_$(date +%Y%m%d).sql

# Restaurar backup (se necessário)
cat backup_20230101.sql | docker exec -i trendpulse_mysql sh -c 'exec mysql -u root -proot trendpulse'
```

Seguindo estas práticas, você manterá sua aplicação TrendPulse atualizada e funcionando de maneira estável, mesmo com mudanças frequentes no código. 

## Contribuindo para o Projeto

Se você deseja contribuir para o desenvolvimento do TrendPulse, siga estas diretrizes:

### 1. Configuração do Ambiente de Desenvolvimento

Recomendamos configurar um ambiente virtual Python:

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual (Windows)
venv\Scripts\activate

# Ativar ambiente virtual (Linux/Mac)
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Instalar dependências de desenvolvimento
pip install pytest pytest-cov black isort flake8
```

### 2. Padrões de Código

Seguimos estas convenções:

- **PEP 8**: Para estilo de código Python
- **Black**: Para formatação automática
- **isort**: Para ordenação de imports
- **Flake8**: Para linting

Antes de enviar uma contribuição, execute:

```bash
# Formatar código
black app tests
isort app tests

# Verificar problemas
flake8 app tests
```

### 3. Testes

Escreva testes para novas funcionalidades e execute a suite de testes antes de enviar alterações:

```bash
# Executar todos os testes
pytest

# Executar com cobertura
pytest --cov=app tests/
```

### 4. Processo de Contribuição

1. **Fork do Repositório**: Crie um fork do repositório principal
2. **Crie uma Branch**: `git checkout -b feature/nova-funcionalidade`
3. **Faça suas Alterações**: Implemente a funcionalidade ou correção
4. **Testes**: Certifique-se de que todos os testes passam
5. **Commit**: Use mensagens de commit claras e descritivas
6. **Push**: Envie suas alterações para seu fork
7. **Pull Request**: Abra um PR para o repositório principal

### 5. Diretrizes para Pull Requests

- Descreva claramente o que sua alteração faz
- Referencie issues relacionadas
- Inclua capturas de tela para alterações visuais
- Certifique-se de que todos os testes passam
- Mantenha o PR focado em uma única alteração

### 6. Relatando Problemas

Ao relatar um problema, inclua:

- Descrição clara do problema
- Passos para reproduzir
- Comportamento esperado vs. comportamento atual
- Logs relevantes
- Ambiente (sistema operacional, versão do Python, etc.)

### 7. Sugestões de Melhorias

Algumas áreas onde você pode contribuir:

- Adicionar novas fontes de tendências
- Melhorar a interface de usuário
- Otimizar o desempenho das tarefas
- Adicionar novos endpoints à API
- Melhorar a documentação
- Implementar testes automatizados

Agradecemos sua contribuição para tornar o TrendPulse ainda melhor! 

## Gerenciamento de Espaço do Banco de Dados

O TrendPulse implementa uma estratégia de retenção de dados para evitar que o banco de dados atinja seu limite de armazenamento, especialmente importante no ambiente de produção onde o PostgreSQL no plano Starter do Render tem um limite de 1GB.

### Estratégia de Retenção de Dados

A aplicação utiliza uma tarefa agendada (`clean_old_trends`) que é executada semanalmente para:

1. **Remover tendências antigas**: Tendências com mais de 60 dias são automaticamente removidas
2. **Limitar o número de registros por plataforma**: Mantém apenas os 5.000 registros mais recentes de cada plataforma
3. **Recuperar espaço físico**: Executa o comando `VACUUM FULL` para liberar espaço no banco de dados

### Configuração da Limpeza

A tarefa de limpeza é configurada no arquivo `app/tasks.py`:

```python
app.conf.beat_schedule.update({
    'clean-old-trends-weekly': {
        'task': 'app.tasks.clean_old_trends',
        'schedule': crontab(day_of_week='sunday', hour=2, minute=0),  # Todo domingo às 2h da manhã
        'kwargs': {'max_days': 60, 'max_records': 5000},
    },
})
```

Você pode ajustar os parâmetros conforme necessário:

- `max_days`: Número máximo de dias para manter as tendências (padrão: 60)
- `max_records`: Número máximo de registros a manter por plataforma (padrão: 5000)

### Monitoramento de Uso do Banco de Dados

Para monitorar o uso de espaço do banco de dados:

#### Usando o Endpoint de Estatísticas

O TrendPulse agora inclui um endpoint específico para monitorar o uso do banco de dados:

```bash
curl http://localhost:8000/api/database/stats
```

Este endpoint retorna informações detalhadas como:
- Tamanho total do banco de dados
- Tamanho de cada tabela
- Número total de tendências
- Contagem de tendências por plataforma
- Informações sobre a tendência mais antiga e mais recente

Exemplo de resposta:
```json
{
  "environment": "development",
  "database_type": "mysql",
  "database_size": {
    "formatted": "45.25 MB",
    "bytes": 47448064
  },
  "tables": {
    "trends": {
      "size": "42.75 MB",
      "bytes": 44826624
    },
    "trend_tags": {
      "size": "2.50 MB",
      "bytes": 2621440
    }
  },
  "total_trends": 8542,
  "trends_by_platform": {
    "youtube": 3256,
    "reddit": 5286
  },
  "oldest_trend": {
    "id": 1,
    "title": "Primeira tendência",
    "platform": "youtube",
    "created_at": "2023-01-15T12:30:45.123456"
  },
  "newest_trend": {
    "id": 8542,
    "title": "Tendência mais recente",
    "platform": "reddit",
    "created_at": "2023-03-20T18:45:12.654321"
  }
}
```

Este endpoint é útil para:
- Monitorar o crescimento do banco de dados
- Identificar quando a limpeza de dados é necessária
- Planejar estratégias de retenção de dados

#### Em Desenvolvimento (MySQL)

```bash
# Verificar tamanho das tabelas
docker exec -it trendpulse_mysql mysql -u root -proot -e "
SELECT 
    table_name AS 'Tabela',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Tamanho (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'trendpulse'
ORDER BY (data_length + index_length) DESC;
"
```

#### Em Produção (PostgreSQL no Render)

No dashboard do Render:
1. Acesse o serviço de banco de dados PostgreSQL
2. Vá para a aba "Metrics"
3. Verifique o gráfico "Disk Usage"

Ou execute uma consulta SQL:

```sql
SELECT
    pg_size_pretty(pg_database_size(current_database())) as db_size,
    pg_size_pretty(pg_total_relation_size('trends')) as trends_size;
```

### Execução Manual da Limpeza

Se necessário, você pode executar a limpeza manualmente:

#### Usando o Endpoint de Limpeza

O TrendPulse agora inclui um endpoint para executar a limpeza do banco de dados manualmente:

```bash
# Limpeza com parâmetros padrão (60 dias, 5000 registros por plataforma)
curl -X POST http://localhost:8000/api/database/cleanup

# Limpeza com parâmetros personalizados
curl -X POST "http://localhost:8000/api/database/cleanup?max_days=30&max_records=1000"
```

Este endpoint inicia a limpeza em segundo plano e retorna imediatamente:

```json
{
  "status": "started",
  "message": "A limpeza do banco de dados foi iniciada em segundo plano",
  "parameters": {
    "max_days": 30,
    "max_records": 1000
  }
}
```

Você pode verificar o progresso da limpeza nos logs do worker:

```bash
docker logs -f trendpulse_worker
```

#### Usando o CLI

Você também pode executar a limpeza diretamente via linha de comando:

```bash
# Em desenvolvimento
docker-compose exec worker python -c "from app.tasks import clean_old_trends; clean_old_trends(max_days=30, max_records=1000)"

# Em produção (Render)
# Use o console do serviço worker no dashboard do Render
```

### Backup Antes da Limpeza

É recomendável fazer um backup antes de executar limpezas manuais:

```bash
# MySQL (desenvolvimento)
docker exec trendpulse_mysql sh -c 'exec mysqldump -u root -proot trendpulse' > backup_antes_limpeza.sql

# PostgreSQL (produção)
# Use a funcionalidade de backup do Render no dashboard
```

### Considerações para Escala

Se o volume de dados continuar crescendo além do limite de 1GB:

1. **Upgrade do Plano**: Considere fazer upgrade para um plano com mais armazenamento
2. **Arquivamento de Dados**: Implemente uma estratégia de arquivamento para dados históricos
3. **Otimização de Esquema**: Revise o esquema do banco para otimizar o armazenamento
4. **Compressão de Dados**: Considere comprimir campos de texto longos

Esta estratégia de retenção de dados garante que o TrendPulse continue funcionando sem interrupções, mesmo com o crescimento contínuo dos dados. 