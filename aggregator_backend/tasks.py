import os
import json
import requests
import requests.auth
from aggregator_backend.celery_app import celery
from aggregator_backend.models import AggregatedContent, SessionLocal
from datetime import datetime

@celery.task
def fetch_twitter_data(keyword):
    """
    Busca tweets recentes com base no termo 'keyword' e salva os resultados no banco.
    """
    bearer_token = os.getenv("TWITTER_BEARER")
    if not bearer_token:
        return {"error": "TWITTER_BEARER not configured"}
    
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "my-aggregator/0.1 by your_twitter_username"
    }
    params = {
        "query": keyword,
        "max_results": 10  # o mínimo é 10, conforme a API do Twitter
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return {"error": response.text}
    
    if response.status_code == 429:
        return {"error": f"Rate limit exceeded, next request available at {datetime.utcfromtimestamp(int(response.headers['x-rate-limit-reset'])).isoformat()}"}
    
    data = response.json()
    tweets = data.get("data", [])
    
    session = SessionLocal()
    for tweet in tweets:
        record = AggregatedContent(
            platform="twitter",
            keyword=keyword,
            title=str(tweet.get("id")),  # Utiliza o ID como título (ajuste conforme necessário)
            content=tweet.get("text", "")
        )
        session.add(record)
    session.commit()
    session.close()
    
    return {"status": "ok", "fetched": len(tweets)}

@celery.task
def fetch_youtube_data(keyword):
    """
    Busca vídeos do YouTube relacionados ao termo 'keyword' e salva os resultados no banco.
    """
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        return {"error": "YOUTUBE_API_KEY not configured"}
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "q": keyword,
        "part": "snippet",
        "type": "video",
        "maxResults": 10,   # mínimo é 10 para a API
        "key": youtube_api_key,
        "order": "viewCount"  # ordena por popularidade (visualizações)
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        return {"error": response.text}
    
    data = response.json()
    items = data.get("items", [])
    
    session = SessionLocal()
    for item in items:
        snippet = item.get("snippet", {})
        record = AggregatedContent(
            platform="youtube",
            keyword=keyword,
            title=snippet.get("title", ""),
            content=json.dumps(item)  # Armazena o JSON completo do item
        )
        session.add(record)
    session.commit()
    session.close()
    
    return {"status": "ok", "fetched": len(items)}

@celery.task
def fetch_reddit_data(keyword):
    """
    Busca posts no Reddit relacionados ao termo 'keyword' utilizando o fluxo de Script App,
    e salva os resultados no banco.
    """
    CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    CLIENT_SECRET = os.getenv("REDDIT_SECRET")
    REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
    REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
    
    if not (CLIENT_ID and CLIENT_SECRET and REDDIT_USERNAME and REDDIT_PASSWORD):
        return {"error": "Reddit credentials not configured"}
    
    user_agent = f"my-aggregator/0.1 by {REDDIT_USERNAME}"
    headers = {"User-Agent": user_agent}
    
    # Autenticação via fluxo de Script App (grant_type=password)
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {
        "grant_type": "password",
        "username": REDDIT_USERNAME,
        "password": REDDIT_PASSWORD
    }
    token_response = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=auth,
        data=data,
        headers=headers
    )
    
    if token_response.status_code != 200:
        return {"error": token_response.text}
    
    token = token_response.json().get("access_token")
    if not token:
        return {"error": "Token not obtained"}
    
    # Atualiza os headers com o token OAuth
    headers["Authorization"] = f"bearer {token}"
    
    params = {
        "q": keyword,
        "sort": "top",
        "limit": 5
    }
    search_response = requests.get(
        "https://oauth.reddit.com/search",
        headers=headers,
        params=params
    )
    
    if search_response.status_code != 200:
        return {"error": search_response.text}
    
    data = search_response.json()
    children = data.get("data", {}).get("children", [])
    
    session = SessionLocal()
    for child in children:
        post = child.get("data", {})
        record = AggregatedContent(
            platform="reddit",
            keyword=keyword,
            title=post.get("title", ""),
            content=json.dumps(post)
        )
        session.add(record)
    session.commit()
    session.close()
    
    return {"status": "ok", "fetched": len(children)}
