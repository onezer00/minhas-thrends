from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
import logging
import os
from aggregator_backend.models import get_db, Trend, create_tables
from aggregator_backend.tasks import fetch_all_trends

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Criar as tabelas no banco de dados, se ainda não existirem
create_tables()

# Configuração de CORS para permitir acesso apenas do GitHub Pages
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "https://<seu-usuario>.github.io")
ALLOWED_ORIGINS = [
    GITHUB_PAGES_URL,
    # URLs para desenvolvimento local
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Configuração de ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_DEVELOPMENT = ENVIRONMENT.lower() == "development"

# Configuração de CORS para permitir acesso apenas do GitHub Pages
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "https://<seu-usuario>.github.io")
ALLOWED_ORIGINS = [
    GITHUB_PAGES_URL,
] if not IS_DEVELOPMENT else [
    # URLs para desenvolvimento local
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app = FastAPI(
    title="TrendPulse API",
    description="API para consulta de tendências de redes sociais",
    version="1.0.0"
)

# Configuração de CORS atualizada
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
    task = fetch_all_trends.delay()
    return {"message": "Tarefa de busca de tendências iniciada", "task_id": task.id}


@app.get("/api/status")
def get_status(db: Session = Depends(get_db)):
    """
    Retorna estatísticas gerais do sistema.
    """
    from sqlalchemy import func
    
    # Total de tendências
    total_trends = db.query(func.count(Trend.id)).scalar()
    
    # Total por plataforma
    platform_counts = db.query(
        Trend.platform, 
        func.count(Trend.id).label("count")
    ).group_by(Trend.platform).all()
    
    # Tendência mais recente
    latest_trend = db.query(Trend).order_by(desc(Trend.created_at)).first()
    latest_date = latest_trend.created_at if latest_trend else None
    
    return {
        "total_trends": total_trends,
        "platform_counts": {p: c for p, c in platform_counts},
        "latest_update": latest_date.isoformat() if latest_date else None,
        "app_version": "1.0.0"
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