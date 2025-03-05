from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import os
import time
from app.models import get_db, Trend, create_tables, SessionLocal
from app.tasks import fetch_all_trends
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
    Retorna as tendências mais recentes, com opções de filtro por plataforma e categoria.
    """
    query = db.query(Trend).order_by(desc(Trend.created_at))
    
    if platform:
        query = query.filter(Trend.platform == platform)
    
    if category:
        query = query.filter(Trend.category == category)
    
    trends = query.offset(skip).limit(limit).all()
    return [trend.to_dict() for trend in trends]


@app.get("/api/trends/{trend_id}")
def get_trend(trend_id: int, db: Session = Depends(get_db)):
    """
    Retorna detalhes de uma tendência específica por ID.
    """
    trend = db.query(Trend).filter(Trend.id == trend_id).first()
    if not trend:
        raise HTTPException(status_code=404, detail="Tendência não encontrada")
    
    return trend.to_dict()


@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    """
    Retorna as categorias disponíveis e o número de tendências em cada uma.
    """
    # Consulta as categorias e conta as tendências em cada uma
    from sqlalchemy import func
    result = db.query(
        Trend.category, 
        func.count(Trend.id).label("count")
    ).group_by(Trend.category).all()
    
    return [{"name": category, "count": count} for category, count in result]


@app.get("/api/platforms")
def get_platforms(db: Session = Depends(get_db)):
    """
    Retorna as plataformas disponíveis e o número de tendências em cada uma.
    """
    from sqlalchemy import func
    result = db.query(
        Trend.platform, 
        func.count(Trend.id).label("count")
    ).group_by(Trend.platform).all()
    
    return [{"name": platform, "count": count} for platform, count in result]


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

@app.get("/api/status", tags=["Status"], response_model=Dict[str, Any])
async def status(force_check: bool = Query(False, description="Força uma nova verificação ignorando o cache")):
    """
    Endpoint para verificar o status da API e suas dependências.
    Usado pelo Render.com para healthcheck.
    
    Por padrão, usa um cache de 60 segundos para reduzir a carga no Redis e banco de dados.
    Use o parâmetro force_check=true para forçar uma nova verificação.
    """
    global status_cache
    
    # Verifica se o cache é válido
    current_time = datetime.utcnow()
    cache_valid = (
        status_cache["last_check"] is not None and
        (current_time - status_cache["last_check"]).total_seconds() < STATUS_CACHE_TTL
    )
    
    # Se o cache for válido e não estamos forçando uma verificação, retorna o cache
    if cache_valid and not force_check:
        return {
            "status": status_cache["status"],
            "redis": status_cache["redis"],
            "database": status_cache["database"],
            "timestamp": status_cache["timestamp"],
            "cached": True,
            "cache_age": int((current_time - status_cache["last_check"]).total_seconds()),
            "cache_ttl": STATUS_CACHE_TTL,
            **({"db_error": status_cache["db_error"]} if status_cache["db_error"] else {}),
            **({"redis_error": status_cache["redis_error"]} if status_cache["redis_error"] else {})
        }
    
    # Caso contrário, faz uma nova verificação
    redis_ok = True
    redis_error = None
    
    try:
        redis_ok = check_redis_connection(verbose=False)
    except Exception as e:
        redis_ok = False
        redis_error = str(e)
        logger.error(f"Erro ao verificar Redis: {str(e)}")
    
    # Verificar conexão com o banco de dados
    db_ok = True
    db_error = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_ok = False
        db_error = str(e)
        logger.error(f"Erro ao verificar banco de dados: {str(e)}")
    
    status_ok = redis_ok and db_ok
    
    # Atualiza o cache
    status_cache = {
        "last_check": current_time,
        "status": "ok" if status_ok else "error",
        "redis": "connected" if redis_ok else "disconnected",
        "database": "connected" if db_ok else "disconnected",
        "timestamp": current_time.isoformat(),
        "db_error": db_error,
        "redis_error": redis_error
    }
    
    response = {
        "status": status_cache["status"],
        "redis": status_cache["redis"],
        "database": status_cache["database"],
        "timestamp": status_cache["timestamp"],
        "cached": False
    }
    
    # Adiciona detalhes do erro se houver
    if db_error:
        response["db_error"] = db_error
    
    if redis_error:
        response["redis_error"] = redis_error
    
    return response


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
async def get_database_stats():
    """
    Retorna estatísticas sobre o uso do banco de dados.
    Inclui tamanho total do banco, tamanho das tabelas e contagem de registros.
    """
    from sqlalchemy import text, func
    from app.models import get_db_session, Trend
    import os
    
    db = get_db_session()
    try:
        stats = {
            "environment": os.getenv("ENVIRONMENT", "development"),
            "database_type": "postgresql" if "postgres" in os.getenv("DATABASE_URL", "").lower() else "mysql",
            "tables": {},
            "total_trends": 0,
            "trends_by_platform": {},
            "oldest_trend": None,
            "newest_trend": None,
        }
        
        # Contagem total de tendências
        stats["total_trends"] = db.query(func.count(Trend.id)).scalar()
        
        # Contagem por plataforma
        platform_counts = db.query(Trend.platform, func.count(Trend.id)).group_by(Trend.platform).all()
        for platform, count in platform_counts:
            stats["trends_by_platform"][platform] = count
        
        # Tendência mais antiga e mais recente
        oldest = db.query(Trend).order_by(Trend.created_at.asc()).first()
        newest = db.query(Trend).order_by(Trend.created_at.desc()).first()
        
        if oldest:
            stats["oldest_trend"] = {
                "id": oldest.id,
                "title": oldest.title,
                "platform": oldest.platform,
                "created_at": oldest.created_at.isoformat(),
            }
        
        if newest:
            stats["newest_trend"] = {
                "id": newest.id,
                "title": newest.title,
                "platform": newest.platform,
                "created_at": newest.created_at.isoformat(),
            }
        
        # Estatísticas específicas por tipo de banco
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
                ORDER BY pg_total_relation_size(quote_ident(tablename)) DESC
            """)
            
            for row in db.execute(table_size_query).fetchall():
                stats["tables"][row.table_name] = {
                    "size": row.size,
                    "bytes": row.bytes
                }
                
        else:
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
                    "formatted": f"{result.size_mb} MB",
                    "bytes": result.bytes
                }
            
            # Tamanho das tabelas
            table_size_query = text("""
                SELECT 
                    table_name,
                    ROUND((data_length + index_length) / 1024 / 1024, 2) as size_mb,
                    (data_length + index_length) as bytes
                FROM information_schema.TABLES
                WHERE table_schema = DATABASE()
                ORDER BY (data_length + index_length) DESC
            """)
            
            for row in db.execute(table_size_query).fetchall():
                stats["tables"][row.table_name] = {
                    "size": f"{row.size_mb} MB",
                    "bytes": row.bytes
                }
        
        return stats
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do banco de dados: {e}")
        return {"error": str(e)}
    finally:
        db.close()


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


if __name__ == "__main__":
    import uvicorn
    # Verifica se o banco está vazio e, se estiver, busca tendências
    with next(get_db()) as db:
        if db.query(Trend).count() == 0:
            logger.info("Banco de dados vazio. Iniciando busca inicial de tendências...")
            fetch_all_trends.delay()
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)