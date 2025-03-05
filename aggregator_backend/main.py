import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from aggregator_backend.models import SessionLocal, AggregatedContent
from aggregator_backend.tasks import fetch_reddit_data, fetch_twitter_data, fetch_youtube_data

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
    title="Aggregator Backend API",
    description="API para agregar conteúdo de Twitter, YouTube e Reddit",
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

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Aggregator Backend API is running"}

@app.get("/trends")
def get_trends(platform: str = None, keyword: str = None):
    """
    Retorna os registros de conteúdo agregado, filtrando por plataforma e/ou keyword.
    Se 'platform' ou 'keyword' não forem fornecidos, retorna os últimos 50 registros.
    """
    db = SessionLocal()
    query = db.query(AggregatedContent)
    
    if platform:
        query = query.filter(AggregatedContent.platform == platform)
    if keyword:
        # Busca case-insensitive para a keyword
        query = query.filter(AggregatedContent.keyword.ilike(f"%{keyword}%"))
    
    records = query.order_by(AggregatedContent.created_at.desc()).limit(50).all()
    db.close()
    
    # Se não houver registros para a plataforma, inicia a busca
    if not platform and not records:
        fetch_youtube_data.delay(keyword)
        fetch_reddit_data.delay(keyword)
        fetch_twitter_data.delay(keyword)
    
    if platform == 'youtube' and not records:
        if not [plat for plat in records if plat.platform == "youtube"]:
            fetch_youtube_data.delay(keyword)
    if platform == 'reddit' and not records:
        if not [plat for plat in records if plat.platform == "reddit"]:
            fetch_reddit_data.delay(keyword)
    if platform == 'twitter' and not records:
        if not [plat for plat in records if plat.platform == "twitter"]:
            fetch_twitter_data.delay(keyword)
    
    results = []
    for record in records:
        try:
            # Tenta decodificar o JSON armazenado em 'content'
            content_parsed = json.loads(record.content) if record.content else {}
        except Exception:
            content_parsed = {}
        
        results.append({
            "id": record.id,
            "platform": record.platform,
            "keyword": record.keyword,
            "title": record.title,
            "content": content_parsed,
            "created_at": record.created_at.isoformat()
        })
    
    return results
