from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from typing import List, Optional
from datetime import datetime
import logging
import os
from app.models import get_db, Trend, create_tables, SessionLocal
from app.tasks import fetch_all_trends
from app.check_db import check_redis_connection

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

# Configuração de CORS para permitir acesso apenas do GitHub Pages
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "https://onezer00.github.io")
ALLOWED_ORIGINS = [
    GITHUB_PAGES_URL,
] if not IS_DEVELOPMENT else [
    # URLs para desenvolvimento local
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

logger.info(f"Ambiente: {ENVIRONMENT}")
logger.info(f"CORS permitido para: {ALLOWED_ORIGINS}")

app = FastAPI(
    title="Aggregator Backend API",
    description="API para agregar conteúdo de YouTube e Reddit",
    version="1.0.0"
)

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas da API

@app.get("/")
def read_root():
    return {"message": "TrendPulse API v1.0"}


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


@app.get("/api/status", tags=["Status"])
async def status():
    """
    Endpoint para verificar o status da API e suas dependências.
    Usado pelo Render.com para healthcheck.
    """
    redis_ok = check_redis_connection()
    
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
    
    response = {
        "status": "ok" if status_ok else "error",
        "redis": "connected" if redis_ok else "disconnected",
        "database": "connected" if db_ok else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Adiciona detalhes do erro se houver
    if db_error:
        response["database_error"] = db_error
    
    # Define o código de status HTTP com base no status
    status_code = 200 if status_ok else 200  # Mantém 200 mesmo com erro para o healthcheck do Render
    
    return response


if __name__ == "__main__":
    import uvicorn
    # Verifica se o banco está vazio e, se estiver, busca tendências
    with next(get_db()) as db:
        if db.query(Trend).count() == 0:
            logger.info("Banco de dados vazio. Iniciando busca inicial de tendências...")
            fetch_all_trends.delay()
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)