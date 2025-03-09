from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import os
import time
from app.models import get_db, Trend, create_tables, SessionLocal
from app.tasks import fetch_all_trends, get_db_session
from app.check_db import check_redis_connection
from fastapi import BackgroundTasks

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Criar as tabelas no banco de dados, se ainda não existirem
create_tables()

# Configuração de ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_DEVELOPMENT = ENVIRONMENT.lower() == "development"

# Função para verificar e corrigir a URL do GitHub Pages
def get_github_pages_url():
    """
    Obtém a URL do GitHub Pages e garante que esteja no formato correto.
    """
    url = os.getenv("GITHUB_PAGES_URL", "https://onezer00.github.io")
    
    # Garante que a URL não termina com barra
    if url.endswith("/"):
        url = url[:-1]
    
    logger.info(f"URL do GitHub Pages: {url}")
    return url

# Configuração de CORS para permitir acesso apenas do GitHub Pages
GITHUB_PAGES_URL = get_github_pages_url()

# Lista de origens permitidas
ALLOWED_ORIGINS = []

# Adiciona variações do GitHub Pages
github_variations = [
    GITHUB_PAGES_URL,
    "https://onezer00.github.io",
    "http://onezer00.github.io",
]

# Adiciona variações com o caminho do projeto
for base in github_variations:
    ALLOWED_ORIGINS.append(base)
    ALLOWED_ORIGINS.append(f"{base}/minhas-trends-frontend")
    ALLOWED_ORIGINS.append(f"{base}/minhas-trends-frontend/")

# Em desenvolvimento, adiciona origens locais
if IS_DEVELOPMENT:
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])

logger.info(f"Ambiente: {ENVIRONMENT}")
logger.info(f"CORS permitido para: {ALLOWED_ORIGINS}")

app = FastAPI(
    title="TrendPulse API",
    description="API para agregação de tendências de várias plataformas",
    version="1.0.0",
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://onezer00\.github\.io(\/.*)?",  # Permite qualquer caminho no domínio onezer00.github.io
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["Content-Length", "Content-Type"],
    max_age=86400,  # Cache por 24 horas
)

# Função para verificar se uma origem está permitida
def is_origin_allowed(origin: str) -> bool:
    """
    Verifica se uma origem está na lista de origens permitidas.
    Considera também casos em que a origem pode ser um subdomínio ou ter um caminho diferente.
    """
    if IS_DEVELOPMENT:
        return True
        
    if not origin or origin == "No Origin":
        return False
        
    # Verifica se a origem está exatamente na lista
    if origin in ALLOWED_ORIGINS:
        return True
        
    # Verifica se a origem é um subdomínio ou tem um caminho diferente
    for allowed in ALLOWED_ORIGINS:
        # Se a origem permitida termina com /, remove para comparação
        if allowed.endswith("/"):
            allowed = allowed[:-1]
            
        # Se a origem atual termina com /, remove para comparação
        if origin.endswith("/"):
            origin = origin[:-1]
            
        # Verifica se a origem atual começa com a origem permitida
        if origin.startswith(allowed):
            return True
            
    return False

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware para logar informações sobre as requisições recebidas,
    especialmente útil para depurar problemas de CORS.
    """
    origin = request.headers.get("origin", "No Origin")
    path = request.url.path
    method = request.method
    
    logger.info(f"Requisição recebida: {method} {path} de {origin}")
    
    # Verifica se a origem está na lista de origens permitidas
    if origin != "No Origin" and not is_origin_allowed(origin):
        logger.warning(f"Origem não permitida: {origin}")
    
    response = await call_next(request)
    
    # Loga o status da resposta
    logger.info(f"Resposta enviada: {response.status_code} para {method} {path}")
    
    return response

# Middleware para lidar com o "adormecimento" no plano Free
@app.middleware("http")
async def handle_free_tier_sleep(request: Request, call_next):
    """
    Middleware para lidar com o "adormecimento" no plano Free do Render.
    Verifica e reconecta ao banco de dados e Redis quando necessário.
    """
    import time
    
    start_time = time.time()
    
    # Executa a requisição normalmente
    response = await call_next(request)
    
    # Verifica se é a primeira requisição após "adormecimento"
    # Uma requisição normal deve levar menos de 1 segundo
    # Se levar mais de 5 segundos, provavelmente o serviço estava "adormecido"
    process_time = time.time() - start_time
    if process_time > 5:
        logger.warning(f"Requisição demorada ({process_time:.2f}s). Verificando conexões após possível 'adormecimento'.")
        
        try:
            # Importa as funções necessárias dentro do bloco try para evitar erros de importação
            from app.models import create_tables
            from app.tasks import check_redis_connection
            
            # Verifica conexão com o banco de dados usando uma função mais simples
            try:
                from app.models import check_db_connection
                db_ok = check_db_connection()
                if not db_ok:
                    logger.warning("Reconectando ao banco de dados após 'adormecimento'...")
                    try:
                        create_tables()
                        logger.info("Reconexão ao banco de dados bem-sucedida!")
                    except Exception as e:
                        logger.error(f"Erro ao reconectar ao banco de dados: {str(e)}")
            except ImportError:
                # Se a função check_db_connection não existir, tenta uma abordagem alternativa
                logger.warning("Função check_db_connection não encontrada. Usando abordagem alternativa.")
                try:
                    create_tables()
                    logger.info("Tabelas verificadas/criadas com sucesso.")
                except Exception as e:
                    logger.error(f"Erro ao verificar/criar tabelas: {str(e)}")
            
            # Verifica conexão com o Redis
            try:
                redis_ok = check_redis_connection(verbose=False)
                redis_status = "connected" if redis_ok else "disconnected"
            except Exception as e:
                logger.error(f"Erro ao verificar status do Redis: {str(e)}")
                redis_status = "error"
        except Exception as e:
            logger.error(f"Erro ao verificar conexões após 'adormecimento': {str(e)}")
    
    return response

# Rotas da API
@app.get("/")
def read_root():
    """
    Rota raiz da API.
    """
    return {
        "message": "Bem-vindo à API TrendPulse",
        "docs": "/docs",
        "status": "/api/status"
    }

@app.get("/api/cors-test")
def cors_test(request: Request):
    """
    Rota para testar a configuração CORS.
    """
    origin = request.headers.get("origin", "No Origin")
    is_allowed = is_origin_allowed(origin)
    
    return {
        "message": "CORS está configurado corretamente!" if is_allowed else "Origem não permitida",
        "origin": origin,
        "is_allowed": is_allowed,
        "allowed_origins": ALLOWED_ORIGINS,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/trends")
def get_trends(
    platform: Optional[str] = Query(None, description="Filtrar por plataforma: twitter, youtube, reddit"),
    category: Optional[str] = Query(None, description="Filtrar por categoria"),
    limit: int = Query(1000, description="Número máximo de resultados", ge=1, le=1000),
    skip: int = Query(0, description="Número de resultados a pular", ge=0),
    db: Session = Depends(get_db)
):
    """
    Retorna as tendências mais recentes.
    Pode ser filtrado por plataforma e categoria.
    """
    try:
        # Consulta base
        query = db.query(Trend).order_by(desc(Trend.created_at))
        
        # Filtros
        if platform:
            query = query.filter(Trend.platform == platform)
        if category:
            query = query.filter(Trend.category == category)
            
        # Paginação
        trends = query.offset(skip).limit(limit).all()
        
        # Retorna os resultados
        return {"trends": [trend.to_dict() for trend in trends]}
    except Exception as e:
        logger.error(f"Erro ao buscar tendências: {str(e)}")
        return {"trends": [], "error": str(e)}


@app.get("/api/trends/{trend_id}")
def get_trend(trend_id: int, db: Session = Depends(get_db)):
    """
    Retorna detalhes de uma tendência específica por ID.
    """
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Tendência não encontrada")
    
    return {"trend": trend.to_dict()}


@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    """
    Retorna as categorias disponíveis e a quantidade de tendências em cada uma.
    """
    try:
        # Conta tendências por categoria
        result = db.query(Trend.category, func.count(Trend.id)).group_by(Trend.category).all()
        
        # Formata o resultado
        return {"categories": [{"name": category, "count": count} for category, count in result]}
    except Exception as e:
        logger.error(f"Erro ao buscar categorias: {str(e)}")
        return {"categories": [], "error": str(e)}


@app.get("/api/platforms")
def get_platforms(db: Session = Depends(get_db)):
    """
    Retorna as plataformas disponíveis e a quantidade de tendências em cada uma.
    """
    try:
        # Conta tendências por plataforma
        result = db.query(Trend.platform, func.count(Trend.id)).group_by(Trend.platform).all()
        
        # Formata o resultado
        return {"platforms": [{"name": platform, "count": count} for platform, count in result]}
    except Exception as e:
        logger.error(f"Erro ao buscar plataformas: {str(e)}")
        return {"platforms": [], "error": str(e)}


@app.post("/api/fetch-trends")
def trigger_fetch_trends():
    """
    Dispara manualmente a tarefa de busca de tendências.
    """
    try:
        # Verificar conexão com Redis antes de disparar a tarefa
        from app.tasks import check_redis_connection
        if not check_redis_connection():
            return {
                "status": "error", 
                "message": "Não foi possível conectar ao Redis. Verifique a configuração."
            }
            
        # Disparar a tarefa
        from app.tasks import fetch_all_trends
        try:
            # Usar apply_async em vez de delay
            task = fetch_all_trends.apply_async()
            return {"message": "Tarefa de busca de tendências iniciada", "task_id": str(task)}
        except Exception as task_error:
            logger.error(f"Erro ao disparar a tarefa: {str(task_error)}")
            # Tentar executar a tarefa diretamente como fallback
            result = fetch_all_trends()
            return {
                "message": "Tarefa executada diretamente (sem Celery)",
                "result": result
            }
    except Exception as e:
        logger.error(f"Erro ao disparar tarefa: {str(e)}")
        return {"status": "error", "message": str(e)}


# Cache para o endpoint de status
status_cache = {
    "last_check": None,
    "status": None,
    "redis": None,
    "database": None,
    "timestamp": None,
    "db_error": None,
    "redis_error": None
}
STATUS_CACHE_TTL = 60  # Tempo de vida do cache em segundos

@app.get("/api/status", tags=["Sistema"])
def get_status():
    """
    Retorna o status atual da API, incluindo conexões com banco de dados e Redis.
    Também inclui informações sobre o ambiente e versão.
    """
    import platform
    
    # Informações do sistema
    system_info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    
    # Verifica conexões
    db_status = "unknown"
    redis_status = "unknown"
    
    try:
        # Tenta importar e usar check_db_connection
        try:
            from app.models import check_db_connection
            db_ok = check_db_connection()
            db_status = "connected" if db_ok else "error"
        except ImportError:
            # Fallback para verificação direta
            try:
                from sqlalchemy.orm import Session
                from app.models import SessionLocal
                db = SessionLocal()
                db.execute(text("SELECT 1"))
                db.close()
                db_status = "connected"
            except Exception as e:
                logger.error(f"Erro ao verificar banco de dados: {str(e)}")
                db_status = "error"
    except Exception as e:
        logger.error(f"Erro ao verificar status do banco de dados: {str(e)}")
        db_status = "error"
    
    try:
        # Tenta verificar o Redis
        from app.tasks import check_redis_connection
        redis_ok = check_redis_connection(verbose=False)
        redis_status = "connected" if redis_ok else "disconnected"
    except Exception as e:
        logger.error(f"Erro ao verificar status do Redis: {str(e)}")
        redis_status = "error"
    
    # Tenta obter informações de memória, mas não falha se não conseguir
    try:
        import psutil
        memory = psutil.virtual_memory()
        system_info["memory"] = {
            "total": f"{memory.total / (1024 * 1024):.1f} MB",
            "available": f"{memory.available / (1024 * 1024):.1f} MB",
            "percent": f"{memory.percent}%"
        }
    except Exception:
        # Ignora erros ao obter informações de memória
        pass
    
    # Status do plano Free
    system_info["free_plan"] = os.environ.get("RENDER_SERVICE_TYPE") == "free"
    
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "version": "1.0.0",
        "database": db_status,
        "redis": redis_status,
        "system_info": system_info
    }


@app.get("/api/config")
def get_config():
    """
    Retorna informações sobre a configuração da API.
    """
    return {
        "environment": ENVIRONMENT,
        "is_development": IS_DEVELOPMENT,
        "github_pages_url": GITHUB_PAGES_URL,
        "allowed_origins": ALLOWED_ORIGINS,
        "cors_enabled": True,
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/database/stats", response_model=Dict[str, Any])
async def get_database_stats(db: Session = Depends(get_db)):
    """
    Retorna estatísticas sobre o uso do banco de dados.
    Inclui tamanho total do banco, tamanho das tabelas e contagem de registros.
    """
    from sqlalchemy import text, func
    from app.models import Trend
    import os
    
    try:
        # Detecta o tipo de banco de dados
        db_url = os.getenv("DATABASE_URL", "").lower()
        
        # Verifica o tipo de banco de dados pela URL ou pela conexão
        if "postgres" in db_url:
            db_type = "postgresql"
        elif "mysql" in db_url:
            db_type = "mysql"
        elif "sqlite" in db_url or ":" not in db_url:
            db_type = "sqlite"
        else:
            # Tenta detectar pelo dialeto da conexão
            try:
                dialect = db.bind.dialect.name.lower()
                if "sqlite" in dialect:
                    db_type = "sqlite"
                elif "postgres" in dialect:
                    db_type = "postgresql"
                elif "mysql" in dialect:
                    db_type = "mysql"
                else:
                    db_type = "unknown"
            except:
                db_type = "unknown"
            
        stats = {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "database_type": db_type,
            "tables": {},
            "total_trends": 0,
            "trends_by_platform": {},
            "oldest_trend": None,
            "newest_trend": None,
            "database_size": {"size": 0, "unit": "bytes"}
        }
        
        # Estatísticas comuns a todos os bancos
        try:
            stats["total_trends"] = db.query(func.count(Trend.id)).scalar()
            
            # Contagem por plataforma
            platform_counts = db.query(Trend.platform, func.count(Trend.id)).group_by(Trend.platform).all()
            stats["trends_by_platform"] = {}
            for platform, count in platform_counts:
                stats["trends_by_platform"][platform] = count
                
            # Tendência mais antiga
            oldest_trend = db.query(Trend).order_by(Trend.created_at).first()
            if oldest_trend:
                stats["oldest_trend"] = {
                    "id": oldest_trend.id,
                    "title": oldest_trend.title,
                    "platform": oldest_trend.platform,
                    "created_at": oldest_trend.created_at.isoformat()
                }
                
            # Tendência mais recente
            newest_trend = db.query(Trend).order_by(Trend.created_at.desc()).first()
            if newest_trend:
                stats["newest_trend"] = {
                    "id": newest_trend.id,
                    "title": newest_trend.title,
                    "platform": newest_trend.platform,
                    "created_at": newest_trend.created_at.isoformat()
                }
        except Exception as e:
            logger.warning(f"Erro ao obter estatísticas básicas: {e}")
        
        # Estatísticas específicas por tipo de banco
        try:
            if stats["database_type"] == "postgresql":
                # PostgreSQL
                db_size_query = text("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                           pg_database_size(current_database()) as bytes
                """)
                result = db.execute(db_size_query).fetchone()
                stats["database_size"] = {
                    "formatted": result.size,
                    "bytes": result.bytes
                }
                
                # Tamanho das tabelas
                table_size_query = text("""
                    SELECT
                        tablename as table_name,
                        pg_size_pretty(pg_total_relation_size(quote_ident(tablename))) as size,
                        pg_total_relation_size(quote_ident(tablename)) as bytes
                    FROM pg_tables
                    WHERE schemaname = 'public'
                """)
                
                for row in db.execute(table_size_query).fetchall():
                    stats["tables"][row.table_name] = {
                        "size": row.size,
                        "bytes": row.bytes
                    }
                    
            elif stats["database_type"] == "mysql":
                # MySQL
                db_size_query = text("""
                    SELECT 
                        table_schema as database_name,
                        ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) as size_mb,
                        SUM(data_length + index_length) as bytes
                    FROM information_schema.TABLES 
                    WHERE table_schema = DATABASE()
                    GROUP BY table_schema
                """)
                
                result = db.execute(db_size_query).fetchone()
                if result:
                    stats["database_size"] = {
                        "size": result.size_mb,
                        "unit": "MB",
                        "bytes": result.bytes
                    }
                else:
                    stats["database_size"] = {"size": 0, "unit": "bytes"}
                
                # Tamanho das tabelas
                table_size_query = text("""
                    SELECT 
                        table_name,
                        ROUND((data_length + index_length) / 1024 / 1024, 2) as size_mb,
                        (data_length + index_length) as bytes,
                        table_rows as row_count
                    FROM information_schema.TABLES
                    WHERE table_schema = DATABASE()
                """)
                
                for row in db.execute(table_size_query).fetchall():
                    stats["tables"][row.table_name] = {
                        "size": row.size_mb,
                        "unit": "MB",
                        "bytes": row.bytes,
                        "rows": row.row_count
                    }
            elif stats["database_type"] == "sqlite":
                # SQLite - informações limitadas
                stats["database_size"] = {"size": 0, "unit": "bytes", "note": "Tamanho não disponível para SQLite"}
                
                # Lista tabelas
                table_list_query = text("SELECT name FROM sqlite_master WHERE type='table';")
                for row in db.execute(table_list_query).fetchall():
                    table_name = row[0]
                    # Conta registros para cada tabela
                    count_query = text(f"SELECT COUNT(*) FROM {table_name}")
                    try:
                        count = db.execute(count_query).scalar()
                        stats["tables"][table_name] = {
                            "rows": count,
                            "note": "Tamanho não disponível para SQLite"
                        }
                    except Exception:
                        # Ignora tabelas que não podem ser consultadas
                        pass
        except Exception as e:
            logger.warning(f"Erro ao obter estatísticas específicas do banco: {e}")
        
        return stats
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do banco de dados: {e}")
        return {"error": str(e)}


@app.post("/api/database/cleanup", response_model=Dict[str, Any])
async def cleanup_database(
    max_days: int = Query(60, description="Número máximo de dias para manter as tendências"),
    max_records: int = Query(5000, description="Número máximo de registros a manter por plataforma"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Executa a limpeza do banco de dados para remover tendências antigas.
    Esta operação é executada em segundo plano para não bloquear a API.
    """
    from app.tasks import clean_old_trends
    
    # Verificar se o usuário tem permissão para executar esta operação
    # Em um ambiente de produção, você deve adicionar autenticação aqui
    
    def run_cleanup():
        try:
            result = clean_old_trends(max_days=max_days, max_records=max_records)
            logger.info(f"Limpeza manual concluída: {result}")
            return result
        except Exception as e:
            logger.error(f"Erro durante a limpeza manual: {e}")
            return {"error": str(e)}
    
    # Adicionar a tarefa para ser executada em segundo plano
    background_tasks.add_task(run_cleanup)
    
    return {
        "status": "started",
        "message": "A limpeza do banco de dados foi iniciada em segundo plano",
        "parameters": {
            "max_days": max_days,
            "max_records": max_records
        }
    }


@app.post("/api/trends/refresh", response_model=Dict[str, Any], status_code=202)
def refresh_trends():
    """
    Inicia uma tarefa para buscar novas tendências de todas as plataformas.
    """
    try:
        # Importa aqui para evitar circular imports
        from app.tasks import fetch_all_trends
        
        # Inicia a tarefa em background
        task = fetch_all_trends.delay()
        
        return {
            "status": "Task initiated",
            "task_id": str(task.id),
            "message": "Busca de tendências iniciada em background"
        }
    except Exception as e:
        logger.error(f"Erro ao iniciar busca de tendências: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao iniciar busca de tendências: {str(e)}"
        )


@app.get("/api/stats", response_model=Dict[str, Any])
async def get_stats():
    """
    Alias para o endpoint /api/database/stats.
    Retorna estatísticas sobre as tendências no banco de dados.
    """
    try:
        return await get_database_stats()
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do banco de dados: {str(e)}")
        # Retorna um objeto vazio estruturado quando ocorre um erro
        import os
        return {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "database_type": "unknown",
            "tables": {},
            "total_trends": 0,
            "trends_by_platform": {},
            "trends_by_category": {},
            "oldest_trend": None,
            "newest_trend": None,
            "database_size": {"size": 0, "unit": "bytes"}
        }


if __name__ == "__main__":
    import uvicorn
    # Verifica se o banco está vazio e, se estiver, busca tendências
    with next(get_db()) as db:
        if db.query(Trend).count() == 0:
            logger.info("Banco de dados vazio. Iniciando busca inicial de tendências...")
            fetch_all_trends.delay()
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)