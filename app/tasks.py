import os
import json
import re
import requests
import requests.auth
from datetime import datetime, timedelta
import logging
from sqlalchemy import func
from app.models import SessionLocal, Trend, TrendTag, AggregatedContent
from app.celery_app import celery
from celery.signals import task_prerun
from celery.schedules import crontab
import redis

# Configuração para o Flower usar menos conexões ao Redis
os.environ['FLOWER_PERSISTENT'] = 'False'  # Desativa persistência para reduzir conexões
os.environ['FLOWER_BROKER_API'] = ''  # Desativa API do broker para reduzir conexões
os.environ['FLOWER_PORT'] = os.environ.get('PORT', '5555')  # Usa a porta definida pelo Render
os.environ['FLOWER_BASIC_AUTH'] = os.environ.get('FLOWER_BASIC_AUTH', '')  # Autenticação básica
os.environ['FLOWER_PURGE_OFFLINE_WORKERS'] = '60'  # Remove workers offline após 60 segundos
os.environ['FLOWER_DB'] = ''  # Desativa banco de dados do Flower
os.environ['FLOWER_MAX_WORKERS'] = '3'  # Limita o número de workers
os.environ['FLOWER_MAX_TASKS'] = '10000'  # Limita o número de tarefas armazenadas

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Definição de periodicidade das tarefas
celery.conf.beat_schedule = {
    # Tarefa principal para buscar todas as tendências a cada 2 horas
    "fetch-all-trends-every-2-hours": {
        "task": "app.tasks.fetch_all_trends",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    # Tarefas específicas para cada plataforma
    "update-twitter-every-3-hours": {
        "task": "app.tasks.fetch_twitter_trends",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "update-youtube-every-3-hours": {
        "task": "app.tasks.fetch_youtube_trends",
        "schedule": crontab(minute=0, hour="*/3"),
    },
    "update-reddit-every-2-hours": {
        "task": "app.tasks.fetch_reddit_trends",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Limpeza de tendências antigas uma vez por dia
    "clean-old-trends-daily": {
        "task": "app.tasks.clean_old_trends",
        "schedule": crontab(minute=0, hour=3),  # 3 AM
    },
}

# Função para verificar conexão com Redis
def check_redis_connection():
    """Verifica a conexão com o Redis e tenta ajustar a URL se necessário."""
    import redis
    import os
    import time
    
    # Obter a URL do broker do Celery
    broker_url = os.environ.get('CELERY_BROKER_URL', '')
    if not broker_url:
        logger.error("CELERY_BROKER_URL não configurada!")
        return False
    
    # Extrair apenas o host e porta para o log (sem credenciais)
    safe_url = broker_url
    if '@' in broker_url:
        safe_url = broker_url.split('@')[1]
    
    logger.info(f"Tentando conectar ao Redis: {safe_url}")
    
    try:
        # Tentar conectar usando a URL do broker
        client = redis.from_url(broker_url)
        ping_result = client.ping()
        logger.info(f"Conexão com Redis bem-sucedida! Ping: {ping_result}")
        return True
    except Exception as e:
        logger.error(f"Erro ao conectar ao Redis: {str(e)}")
        
        # Tentar extrair o host do Redis da URL
        if 'redis://' in broker_url:
            try:
                # Extrair o host do Redis
                host_part = broker_url.split('redis://')[1].split(':')[0]
                if '@' in host_part:
                    host_part = host_part.split('@')[1]
                
                # Tentar diferentes formatos de URL
                alternate_urls = [
                    f"redis://{host_part}:6379/0",
                    f"redis://trendpulse-redis:6379/0",
                    f"redis://trendpulse-redis.internal:6379/0",
                    f"redis://localhost:6379/0"
                ]
                
                for url in alternate_urls:
                    try:
                        logger.info(f"Tentando URL alternativa: {url}")
                        client = redis.from_url(url)
                        if client.ping():
                            logger.info(f"Conexão bem-sucedida com URL alternativa: {url}")
                            
                            # Atualizar as variáveis de ambiente
                            os.environ['CELERY_BROKER_URL'] = url
                            os.environ['CELERY_RESULT_BACKEND'] = url
                            
                            # Tentar atualizar a configuração do Celery
                            try:
                                from app.celery_app import celery
                                celery.conf.broker_url = url
                                celery.conf.result_backend = url
                                logger.info("Configuração do Celery atualizada")
                            except Exception as ce:
                                logger.warning(f"Não foi possível atualizar a configuração do Celery: {str(ce)}")
                            
                            return True
                    except Exception as inner_e:
                        logger.warning(f"Falha com URL alternativa {url}: {str(inner_e)}")
            except Exception as parse_e:
                logger.error(f"Erro ao analisar a URL do Redis: {str(parse_e)}")
        
        return False

# Hook para verificar conexão antes de cada task
@task_prerun.connect
def check_redis_before_task(task_id, task, *args, **kwargs):
    """Verifica a conexão com o Redis antes de executar uma task."""
    try:
        logger.debug(f"Verificando conexão com Redis antes de executar task {task.name}")
        check_redis_connection()
    except Exception as e:
        logger.error(f"Erro ao verificar conexão com Redis: {str(e)}")
        # Não levantamos a exceção para permitir que a task continue
        # mesmo se a verificação falhar

# Verifica se o banco de dados está vazio na inicialização
@celery.on_after_configure.connect
def setup_initial_tasks(sender, **kwargs):
    """
    Função que verifica se o banco está vazio e, em caso positivo,
    dispara a busca de tendências imediatamente.
    """
    # Verifica se está rodando no serviço Flower
    service = os.environ.get('SERVICE', '')
    if service == 'flower':
        logger.info("Rodando como serviço Flower, pulando verificação do banco de dados.")
        return
    
    # Verificar conexão com Redis antes de prosseguir
    if not check_redis_connection():
        logger.error("Não foi possível conectar ao Redis. Pulando inicialização de tarefas.")
        return
        
    try:
        # Importa os modelos e conexão com o banco
        from app.models import SessionLocal, Trend
        
        # Cria uma sessão
        db = SessionLocal()
        
        # Verifica se existem tendências no banco
        trend_count = db.query(func.count(Trend.id)).scalar()
        
        # Fecha a sessão
        db.close()
        
        if trend_count == 0:
            logger.info("Banco de dados vazio. Iniciando busca inicial de tendências...")
            # Dispara as tarefas de busca de tendências imediatamente
            try:
                # Usar apply_async em vez de delay
                task = fetch_all_trends.apply_async()
                logger.info(f"Tarefa de busca inicial agendada com ID: {task}")
            except Exception as e:
                logger.error(f"Erro ao agendar tarefa inicial: {str(e)}")
                # Tentar executar diretamente como fallback
                logger.info("Tentando executar a tarefa diretamente...")
                result = fetch_all_trends()
                logger.info(f"Resultado da execução direta: {result}")
        else:
            logger.info(f"Banco de dados contém {trend_count} tendências. Seguindo agendamento normal.")
    except Exception as e:
        logger.error(f"Erro ao verificar o banco de dados: {str(e)}")

@celery.task
def fetch_all_trends():
    """
    Tarefa principal que dispara a busca de tendências em todas as plataformas.
    """
    # Verificar conexão com Redis antes de prosseguir
    if not check_redis_connection():
        logger.error("Não foi possível conectar ao Redis. Abortando tarefa fetch_all_trends.")
        return {
            "status": "error",
            "mensagem": "Falha na conexão com Redis",
            "atualizacoes": {}
        }
        
    try:
        logger.info("Iniciando busca de tendências em todas as plataformas...")
        
        # Dicionário para armazenar o status de cada atualização
        atualizacoes = {}
        
        # YouTube
        try:
            # Importar a tarefa localmente para evitar problemas de importação circular
            youtube_task = fetch_youtube_trends
            # Chamar a tarefa diretamente em vez de usar delay()
            youtube_task_id = youtube_task.apply_async()
            atualizacoes["youtube"] = {
                "executado": True,
                "mensagem": f"Iniciada atualização do YouTube (task_id: {youtube_task_id})"
            }
        except Exception as e:
            logger.error(f"Erro ao iniciar busca do YouTube: {str(e)}")
            atualizacoes["youtube"] = {
                "executado": False,
                "mensagem": f"Erro: {str(e)}"
            }
        
        # Reddit
        try:
            # Importar a tarefa localmente para evitar problemas de importação circular
            reddit_task = fetch_reddit_trends
            # Chamar a tarefa diretamente em vez de usar delay()
            reddit_task_id = reddit_task.apply_async()
            atualizacoes["reddit"] = {
                "executado": True,
                "mensagem": f"Iniciada atualização do Reddit (task_id: {reddit_task_id})"
            }
        except Exception as e:
            logger.error(f"Erro ao iniciar busca do Reddit: {str(e)}")
            atualizacoes["reddit"] = {
                "executado": False,
                "mensagem": f"Erro: {str(e)}"
            }
        
        # Twitter (desativado temporariamente)
        atualizacoes["twitter"] = {
            "executado": False,
            "mensagem": "Twitter temporariamente desativado"
        }
        
        resultado = {
            "status": "ok",
            "atualizacoes": atualizacoes
        }
        
        logger.info(f"Relatório de atualizações: {json.dumps(resultado, indent=2)}")
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao executar fetch_all_trends: {str(e)}")
        return {
            "status": "error",
            "mensagem": str(e),
            "atualizacoes": {}
        }


# @celery.task
def fetch_twitter_trends():
    """
    Busca as principais tendências do Twitter e salva no banco.
    """
    bearer_token = os.getenv("TWITTER_BEARER")
    if not bearer_token:
        logger.error("TWITTER_BEARER não configurado")
        return {"error": "TWITTER_BEARER not configured"}
    
    # Endpoint para obter trending topics do Twitter (WOEID 1 = Global, 23424768 = Brasil)
    woeid = 23424768  # WOEID para Brasil
    url = f"https://api.x.com/2/trends/by/woeid/{woeid}"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "TrendPulse/1.0"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Erro na API do Twitter: {response.text}")
            return {"error": response.text}
        
        data = response.json()
        trends = data[0]["trends"] if data and len(data) > 0 else []
        
        session = SessionLocal()
        trend_count = 0
        
        # Salva cada tendência no banco de dados
        for trend_info in trends[:20]:  # Limita a 20 tendências
            # Verifica se a tendência já existe para evitar duplicatas
            existing_trend = session.query(Trend).filter(
                Trend.platform == "twitter",
                Trend.title == trend_info["name"]
            ).first()
            
            if not existing_trend:
                # Para cada tendência, busca tweets relacionados
                tweets = fetch_twitter_data_by_trend(trend_info["name"], bearer_token)
                
                # Extrai hashtags do nome da tendência
                hashtags = extract_hashtags(trend_info["name"])
                
                # Determina o autor da tendência (neste caso, usamos o Twitter como autor)
                author = "@TwitterTrends"
                if tweets and len(tweets) > 0:
                    # Ou usa o autor do tweet mais relevante
                    author = f"@{tweets[0].get('user', {}).get('screen_name', 'Twitter')}"
                
                # Cria um registro de tendência
                trend = Trend(
                    platform="twitter",
                    title=trend_info["name"],
                    description=f"Volume de tweets: {trend_info.get('tweet_volume', 'N/A')}",
                    category=classify_trend_category(trend_info["name"]),
                    external_id=str(trend_info.get("query", "")),
                    author=author,
                    views=trend_info.get("tweet_volume", 0) or 0,
                    likes=0,
                    comments=0,
                    published_at=datetime.utcnow(),
                    content=json.dumps(trend_info),
                    volume=trend_info.get("tweet_volume", 0) or 0
                )
                session.add(trend)
                session.flush()  # Para obter o ID da tendência
                
                # Adiciona as tags
                for hashtag in hashtags:
                    tag = TrendTag(trend_id=trend.id, name=hashtag)
                    session.add(tag)
                
                # Adiciona os tweets como conteúdo agregado vinculado à tendência
                for tweet in tweets:
                    content = AggregatedContent(
                        trend_id=trend.id,
                        platform="twitter",
                        title=tweet.get("text", ""),
                        content=json.dumps(tweet),
                        author=f"@{tweet.get('user', {}).get('screen_name', '')}",
                        likes=tweet.get("favorite_count", 0),
                        comments=tweet.get("reply_count", 0),
                        views=0
                    )
                    session.add(content)
                
                trend_count += 1
        
        session.commit()
        session.close()
        
        logger.info(f"Salvou {trend_count} tendências do Twitter")
        return {"status": "ok", "trends_saved": trend_count}
    
    except Exception as e:
        logger.error(f"Erro ao buscar tendências do Twitter: {str(e)}")
        return {"error": str(e)}


def fetch_twitter_data_by_trend(trend_name, bearer_token):
    """
    Função auxiliar para buscar tweets relacionados a uma tendência específica.
    """
    if not bearer_token:
        return []
    
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "TrendPulse/1.0"
    }
    
    # Remove caracteres especiais e prepara a query
    query = trend_name.replace("#", "")
    
    params = {
        "query": query,
        "max_results": 10,
        "tweet.fields": "created_at,public_metrics,attachments",
        "expansions": "author_id,attachments.media_keys",
        "user.fields": "name,username,profile_image_url"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            logger.warning(f"Erro ao buscar tweets para {trend_name}: {response.text}")
            return []
        
        data = response.json()
        tweets = data.get("data", [])
        users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
        
        # Adiciona informações dos usuários aos tweets
        for tweet in tweets:
            author_id = tweet.get("author_id")
            if author_id and author_id in users:
                tweet["user"] = users[author_id]
                
            # Extraindo métricas
            metrics = tweet.get("public_metrics", {})
            tweet["reply_count"] = metrics.get("reply_count", 0)
            tweet["retweet_count"] = metrics.get("retweet_count", 0)
            tweet["like_count"] = metrics.get("like_count", 0)
            tweet["favorite_count"] = metrics.get("like_count", 0)  # Alias para compatibilidade
        
        return tweets
    except Exception as e:
        logger.error(f"Erro ao buscar tweets para a tendência {trend_name}: {str(e)}")
        return []


@celery.task
def fetch_youtube_trends():
    """
    Busca os vídeos em tendência no YouTube e salva no banco.
    Otimizado para usar menos cotas da API:
    - Reduzido para 10 vídeos por requisição
    - Adicionado controle de erros melhor
    - Cache de respostas de erro para evitar chamadas repetidas
    """
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        logger.error("YOUTUBE_API_KEY não configurado")
        return {"error": "YOUTUBE_API_KEY not configured"}
    
    # Endpoint para buscar vídeos em tendência
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",  # Removido contentDetails para economizar cotas
        "chart": "mostPopular",
        "regionCode": "BR",  # Brasil
        "maxResults": 10,    # Reduzido para 10 vídeos
        "key": youtube_api_key
    }
    
    try:
        session = SessionLocal()
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            error_msg = f"Erro na API do YouTube: {response.text}"
            logger.error(error_msg)
            session.close()
            return {"error": error_msg}
        
        data = response.json()
        items = data.get("items", [])
        trend_count = 0
        
        for item in items:
            snippet = item.get("snippet", {})
            video_id = item.get("id")
            
            # Verifica se a tendência já existe
            existing_trend = session.query(Trend).filter(
                Trend.platform == "youtube",
                Trend.external_id == video_id
            ).first()
            
            if not existing_trend:
                try:
                    # Extrai tags do vídeo (limitado a 3 para reduzir volume de dados)
                    video_tags = snippet.get("tags", [])[:3]
                    
                    # Calcula a data de publicação
                    published_at = datetime.fromisoformat(snippet.get("publishedAt").replace("Z", "+00:00"))
                    
                    # Cria o registro de tendência
                    trend = Trend(
                        platform="youtube",
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        external_id=video_id,
                        category=classify_trend_category(snippet.get("title", "")),
                        author=snippet.get("channelTitle", ""),
                        thumbnail=snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                        views=int(item.get("statistics", {}).get("viewCount", 0)),
                        likes=int(item.get("statistics", {}).get("likeCount", 0)),
                        comments=int(item.get("statistics", {}).get("commentCount", 0)),
                        published_at=published_at,
                        content=json.dumps({
                            "id": video_id,
                            "title": snippet.get("title", ""),
                            "channelTitle": snippet.get("channelTitle", ""),
                            "statistics": item.get("statistics", {})
                        }),
                        volume=int(item.get("statistics", {}).get("viewCount", 0)),
                        url=f"https://www.youtube.com/watch?v={video_id}"
                    )
                    session.add(trend)
                    session.flush()
                    
                    # Adiciona as tags
                    for tag in video_tags:
                        tag_entry = TrendTag(trend_id=trend.id, name=tag)
                        session.add(tag_entry)
                    
                    # Adiciona o vídeo como conteúdo agregado com dados reduzidos
                    content = AggregatedContent(
                        trend_id=trend.id,
                        platform="youtube",
                        title=snippet.get("title", ""),
                        content=json.dumps({
                            "id": video_id,
                            "statistics": item.get("statistics", {})
                        }),  # Conteúdo reduzido
                        author=snippet.get("channelTitle", ""),
                        likes=int(item.get("statistics", {}).get("likeCount", 0)),
                        comments=int(item.get("statistics", {}).get("commentCount", 0)),
                        views=int(item.get("statistics", {}).get("viewCount", 0))
                    )
                    session.add(content)
                    
                    trend_count += 1
                except Exception as item_error:
                    logger.warning(f"Erro ao processar vídeo {video_id}: {str(item_error)}")
                    continue
        
        session.commit()
        session.close()
        
        logger.info(f"Salvou {trend_count} tendências do YouTube")
        return {"status": "ok", "trends_saved": trend_count}
    
    except Exception as e:
        logger.error(f"Erro ao buscar tendências do YouTube: {str(e)}")
        if 'session' in locals():
            session.close()
        return {"error": str(e)}


@celery.task
def fetch_reddit_trends():
    """
    Busca os posts em tendência no Reddit e salva no banco.
    """
    CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    CLIENT_SECRET = os.getenv("REDDIT_SECRET")
    REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
    REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
    
    if not (CLIENT_ID and CLIENT_SECRET and REDDIT_USERNAME and REDDIT_PASSWORD):
        logger.error("Credenciais do Reddit não configuradas")
        return {"error": "Reddit credentials not configured"}
    
    user_agent = f"TrendPulse/1.0 by {REDDIT_USERNAME}"
    headers = {"User-Agent": user_agent}
    
    try:
        # Autenticação via fluxo de Script App
        auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
        data = {
            "grant_type": "password",
            "username": REDDIT_USERNAME,
            "password": REDDIT_PASSWORD
        }
        
        logger.info("Tentando autenticar no Reddit...")
        logger.debug(f"Usando client_id: {CLIENT_ID[:4]}... e username: {REDDIT_USERNAME}")
        
        token_response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data=data,
            headers=headers
        )
        
        if token_response.status_code != 200:
            error_msg = f"Erro na autenticação do Reddit: Status {token_response.status_code} - {token_response.text}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        token_data = token_response.json()
        logger.debug(f"Resposta da autenticação: {token_data}")
        
        if not isinstance(token_data, dict):
            error_msg = f"Resposta de token inválida: {token_data}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        token = token_data.get("access_token")
        if not token:
            error_msg = "Token não encontrado na resposta"
            logger.error(error_msg)
            return {"error": error_msg}
        
        logger.info("Autenticação no Reddit bem-sucedida")
        
        # Atualiza os headers com o token OAuth
        headers["Authorization"] = f"bearer {token}"
        
        # Busca posts em tendência de vários subreddits populares
        subreddits = ["popular", "brasil", "technology", "programming", "science"]
        session = SessionLocal()
        trend_count = 0
        
        for subreddit in subreddits:
            try:
                logger.info(f"Buscando posts do subreddit: {subreddit}")
                url = f"https://oauth.reddit.com/r/{subreddit}/hot"
                logger.debug(f"URL da requisição: {url}")
                logger.debug(f"Headers: {headers}")
                
                response = requests.get(
                    url,
                    headers=headers,
                    params={"limit": 5}
                )
                
                if response.status_code != 200:
                    logger.error(f"Erro ao buscar posts do subreddit {subreddit}: Status {response.status_code} - {response.text}")
                    continue
                
                response_data = response.json()
                logger.debug(f"Resposta do subreddit {subreddit}: {response_data}")
                
                if not isinstance(response_data, dict):
                    logger.warning(f"Resposta inválida do subreddit {subreddit}: {response_data}")
                    continue
                
                data = response_data.get("data")
                if not data:
                    logger.warning(f"Dados ausentes na resposta do subreddit {subreddit}")
                    continue
                
                children = data.get("children", [])
                logger.info(f"Encontrados {len(children)} posts em {subreddit}")
                
                for child in children:
                    try:
                        post = child.get("data")
                        if not post:
                            logger.warning("Post sem dados, pulando...")
                            continue
                            
                        post_id = post.get("id")
                        if not post_id:
                            logger.warning("Post sem ID, pulando...")
                            continue
                        
                        logger.debug(f"Processando post {post_id} do subreddit {subreddit}")
                        
                        # Cria um identificador único combinando subreddit e post_id
                        unique_id = f"{subreddit}_{post_id}"
                        
                        # Verifica se a tendência já existe usando o identificador único
                        existing_trend = session.query(Trend).filter(
                            Trend.platform == "reddit",
                            Trend.external_id == unique_id
                        ).first()
                        
                        if not existing_trend:
                            # Calcula a data de publicação
                            published_at = datetime.fromtimestamp(post.get("created_utc", datetime.utcnow().timestamp()))
                            
                            # Extrai tags do título e subreddit
                            tags = [post.get("subreddit", "").lower()]
                            if "flair" in post and post.get("link_flair_text"):
                                tags.append(post.get("link_flair_text").lower())
                            
                            # Obtém descrição e thumbnail com tratamento de erro
                            try:
                                description = get_reddit_description(post)
                                logger.debug(f"Descrição obtida para o post {post_id}: {description[:100]}...")
                            except Exception as desc_error:
                                logger.warning(f"Erro ao obter descrição do post {post_id}: {str(desc_error)}")
                                description = "Descrição não disponível"

                            try:
                                thumbnail = get_reddit_thumbnail(post)
                                logger.debug(f"Thumbnail obtido para o post {post_id}: {thumbnail}")
                            except Exception as thumb_error:
                                logger.warning(f"Erro ao obter thumbnail do post {post_id}: {str(thumb_error)}")
                                thumbnail = None
                            
                            # Cria o registro de tendência com o identificador único
                            trend = Trend(
                                platform="reddit",
                                title=post.get("title", ""),
                                description=description,
                                external_id=unique_id,  # Usando o identificador único aqui
                                category=classify_trend_category(post.get("title", "") + " " + post.get("subreddit", "")),
                                author=f"u/{post.get('author', '')}",
                                thumbnail=thumbnail,
                                views=post.get("view_count", 0) or post.get("score", 0) * 5,
                                likes=int(post.get("score", 0)),
                                comments=int(post.get("num_comments", 0)),
                                published_at=published_at,
                                content=json.dumps(post),
                                volume=int(post.get("score", 0)),
                                url=f"https://www.reddit.com{post.get('permalink', '')}"
                            )
                            session.add(trend)
                            session.flush()
                            
                            logger.debug(f"Tendência criada para o post {post_id}")
                            
                            # Adiciona as tags
                            for tag in tags:
                                tag_entry = TrendTag(trend_id=trend.id, name=tag)
                                session.add(tag_entry)
                            
                            # Adiciona o post como conteúdo agregado
                            content = AggregatedContent(
                                trend_id=trend.id,
                                platform="reddit",
                                title=post.get("title", ""),
                                content=json.dumps({
                                    "id": post_id,
                                    "subreddit": post.get("subreddit", ""),
                                    "score": post.get("score", 0),
                                    "num_comments": post.get("num_comments", 0)
                                }),
                                author=f"u/{post.get('author', '')}",
                                likes=int(post.get("score", 0)),
                                comments=int(post.get("num_comments", 0)),
                                views=post.get("view_count", 0) or post.get("score", 0) * 5
                            )
                            session.add(content)
                            
                            trend_count += 1
                            logger.debug(f"Conteúdo agregado criado para o post {post_id}")
                            
                    except Exception as post_error:
                        logger.error(f"Erro ao processar post {post_id if 'post_id' in locals() else 'desconhecido'}: {str(post_error)}")
                        continue
                
                # Commit após cada subreddit para garantir que alguns dados sejam salvos mesmo se houver erro
                try:
                    session.commit()
                    logger.info(f"Commit realizado com sucesso para o subreddit {subreddit}")
                except Exception as commit_error:
                    logger.error(f"Erro ao fazer commit dos dados do subreddit {subreddit}: {str(commit_error)}")
                    session.rollback()
                    
            except Exception as subreddit_error:
                logger.error(f"Erro ao processar subreddit {subreddit}: {str(subreddit_error)}")
                session.rollback()
                continue
        
        session.close()
        logger.info(f"Salvou {trend_count} tendências do Reddit")
        return {"status": "ok", "trends_saved": trend_count}
    
    except Exception as e:
        logger.error(f"Erro ao buscar tendências do Reddit: {str(e)}")
        if 'session' in locals():
            session.close()
        return {"error": str(e)}


def get_reddit_description(post):
    """
    Extrai a descrição mais apropriada de um post do Reddit.
    """
    if not isinstance(post, dict):
        logger.warning("Post inválido recebido em get_reddit_description")
        return "Descrição não disponível"
    
    description_parts = []
    
    # Se for um texto (self post)
    if post.get("selftext"):
        return post.get("selftext")
    
    # Se for um link
    if post.get("url"):
        description_parts.append(f"Link: {post.get('url')}")
    
    # Se for uma imagem
    if post.get("post_hint") == "image":
        description_parts.append(f"Imagem: {post.get('url')}")
    
    # Se for um vídeo
    if post.get("is_video"):
        if post.get("media", {}).get("reddit_video", {}).get("fallback_url"):
            description_parts.append(f"Vídeo: {post['media']['reddit_video']['fallback_url']}")
    
    # Se for um link para galeria
    if post.get("is_gallery"):
        gallery_items = []
        for item in post.get("gallery_data", {}).get("items", []):
            media_id = item.get("media_id")
            if media_id:
                url = post.get("media_metadata", {}).get(media_id, {}).get("s", {}).get("u")
                if url:
                    gallery_items.append(url)
        if gallery_items:
            description_parts.append("Galeria de imagens:")
            description_parts.extend(gallery_items)
    
    # Se tiver uma prévia de mídia
    if post.get("preview", {}).get("images"):
        first_image = post["preview"]["images"][0]
        if first_image.get("source", {}).get("url"):
            description_parts.append(f"Prévia: {first_image['source']['url']}")
    
    return "\n".join(description_parts) if description_parts else "Sem descrição disponível"


def get_reddit_thumbnail(post):
    """
    Extrai a melhor thumbnail disponível de um post do Reddit.
    """
    if not isinstance(post, dict):
        logger.warning("Post inválido recebido em get_reddit_thumbnail")
        return None
        
    # Tenta obter a thumbnail específica do post
    if post.get("thumbnail") and post["thumbnail"].startswith("http"):
        return post["thumbnail"]
    
    # Se for uma imagem, usa a própria imagem como thumbnail
    if post.get("post_hint") == "image" and post.get("url"):
        return post["url"]
    
    # Se tiver preview de imagem
    if post.get("preview", {}).get("images"):
        first_image = post["preview"]["images"][0]
        if first_image.get("source", {}).get("url"):
            return first_image["source"]["url"]
    
    return None


@celery.task
def clean_old_trends():
    """
    Remove tendências antigas para manter o banco de dados limpo.
    Mantém apenas os últimos 7 dias de tendências.
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        session = SessionLocal()
        
        # Conta quantas tendências serão removidas
        count_query = session.query(func.count(Trend.id)).filter(Trend.created_at < cutoff_date)
        trends_to_remove = count_query.scalar()
        
        # Remove tendências antigas
        delete_query = session.query(Trend).filter(Trend.created_at < cutoff_date).delete()
        
        session.commit()
        session.close()
        
        logger.info(f"Removidas {trends_to_remove} tendências antigas")
        return {"status": "ok", "trends_removed": trends_to_remove}
    
    except Exception as e:
        logger.error(f"Erro ao limpar tendências antigas: {str(e)}")
        return {"error": str(e)}


def extract_hashtags(text):
    """
    Extrai hashtags do texto.
    """
    hashtag_pattern = r'#(\w+)'
    hashtags = re.findall(hashtag_pattern, text)
    return hashtags


def classify_trend_category(text):
    """
    Função para classificar uma tendência em uma categoria com base no texto.
    """
    text = text.lower()
    
    categories = {
        "tecnologia": ["tech", "tecnologia", "programming", "code", "software", "hardware", "ai", "ia", "inteligência artificial", "app", "smartphone", "iphone", "android"],
        "entretenimento": ["music", "música", "film", "filme", "series", "série", "tv", "cinema", "entertainment", "game", "jogo", "netflix", "streaming", "hollywood", "show"],
        "esportes": ["sport", "esporte", "football", "futebol", "soccer", "basketball", "basquete", "nba", "fifa", "olympics", "olimpíadas", "atleta", "championship"],
        "ciência": ["science", "ciência", "research", "pesquisa", "discovery", "descoberta", "space", "espaço", "nasa", "biology", "biologia", "physics", "física", "chemistry", "química"],
        "finanças": ["finance", "finanças", "economy", "economia", "market", "mercado", "stock", "ação", "invest", "investimento", "bank", "banco", "bitcoin", "crypto", "money", "dinheiro"],
        "política": ["politics", "política", "government", "governo", "election", "eleição", "president", "presidente", "congress", "congresso", "democracy", "democracia"],
        "saúde": ["health", "saúde", "covid", "vaccine", "vacina", "doctor", "médico", "hospital", "disease", "doença", "treatment", "tratamento", "medicine", "medicina"]
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return category
    
    return "outros"  # Categoria padrão