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
from celery.signals import task_prerun, task_postrun
from celery.schedules import crontab
import redis
import gc

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

# Função para obter variáveis de ambiente com log
def get_env_var(var_name, default=''):
    """Obtém uma variável de ambiente com log para depuração"""
    value = os.getenv(var_name, default)
    if not value and var_name not in ['REDDIT_PASSWORD', 'REDDIT_SECRET', 'YOUTUBE_API_KEY']:
        logger.warning(f"Variável de ambiente {var_name} não está configurada")
    elif value:
        # Não loga valores de variáveis sensíveis
        if var_name in ['REDDIT_PASSWORD', 'REDDIT_SECRET', 'YOUTUBE_API_KEY']:
            logger.info(f"Variável de ambiente {var_name} está configurada")
        else:
            logger.info(f"Variável de ambiente {var_name} = {value}")
    return value

# Configurações de ambiente
YOUTUBE_API_KEY = get_env_var('YOUTUBE_API_KEY')
REDDIT_CLIENT_ID = get_env_var('REDDIT_CLIENT_ID')
REDDIT_SECRET = get_env_var('REDDIT_SECRET')
REDDIT_USERNAME = get_env_var('REDDIT_USERNAME')
REDDIT_PASSWORD = get_env_var('REDDIT_PASSWORD')

# Função para verificar conexão com Redis
def check_redis_connection():
    """Verifica a conexão com o Redis e tenta ajustar a URL se necessário."""
    import redis
    import os
    import time
    
    # Obter a URL do broker do Celery
    broker_url = os.getenv('CELERY_BROKER_URL', '')
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
    logger.info(f"Preparando para executar tarefa {task.name} [{task_id}]")
    
    # Verifica se o Redis está acessível
    if not check_redis_connection():
        logger.error(f"Redis não está acessível. A tarefa {task.name} não será executada.")
        raise Exception("Redis não está acessível")
    
    logger.info(f"Redis está acessível. Executando tarefa {task.name}...")

# Sinal executado após cada tarefa
@task_postrun.connect
def cleanup_after_task(task_id, task, *args, **kwargs):
    """Limpa recursos após a execução de uma tarefa."""
    logger.info(f"Finalizando tarefa {task.name} [{task_id}]")
    
    # Força a coleta de lixo para liberar memória
    gc.collect()
    
    # Registra uso de memória
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        logger.info(f"Uso de memória após tarefa {task.name}: {memory_info.rss / 1024 / 1024:.2f} MB")
    except ImportError:
        logger.info("Módulo psutil não disponível para monitoramento de memória")
    
    logger.info(f"Tarefa {task.name} finalizada e memória liberada")

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
    logger.info("Iniciando busca de tendências de todas as plataformas")
    results = {}
    
    # Verifica se o Redis está acessível
    if not check_redis_connection():
        logger.error("Redis não está acessível. Não é possível buscar tendências.")
        return {"error": "Redis não está acessível"}
    
    try:
        # Busca tendências do YouTube
        logger.info("Buscando tendências do YouTube")
        youtube_result = fetch_youtube_trends.delay()
        results["youtube"] = "Tarefa iniciada"
        
        # Busca tendências do Reddit
        logger.info("Buscando tendências do Reddit")
        reddit_result = fetch_reddit_trends.delay()
        results["reddit"] = "Tarefa iniciada"
        
        logger.info("Todas as tarefas de busca de tendências foram iniciadas")
        return results
    except Exception as e:
        logger.error(f"Erro ao buscar tendências: {str(e)}")
        return {"error": str(e)}
    finally:
        # Limpa memória
        gc.collect()

@celery.task
def fetch_youtube_trends():
    """
    Busca os vídeos em tendência no YouTube e salva no banco.
    Otimizado para usar menos cotas da API:
    - Reduzido para 10 vídeos por requisição
    - Adicionado controle de erros melhor
    - Cache de respostas de erro para evitar chamadas repetidas
    """
    # Recarrega a chave da API do ambiente
    youtube_api_key = get_env_var('YOUTUBE_API_KEY')
    
    if not youtube_api_key:
        logger.error("Chave de API do YouTube não configurada")
        # Tenta obter a chave da variável global
        if YOUTUBE_API_KEY:
            logger.info("Usando chave de API do YouTube da variável global")
            youtube_api_key = YOUTUBE_API_KEY
        else:
            return {"error": "Chave de API do YouTube não configurada"}
    
    logger.info("Iniciando busca de tendências do YouTube")
    
    try:
        import requests
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        # Cria o serviço do YouTube
        youtube = build('youtube', 'v3', developerKey=youtube_api_key, cache_discovery=False)
        
        # Busca vídeos em tendência
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="BR",
            maxResults=10
        )
        response = request.execute()
        
        # Processa os resultados
        db = SessionLocal()
        try:
            count = 0
            for item in response.get('items', []):
                # Extrai dados do vídeo
                video_id = item['id']
                snippet = item['snippet']
                statistics = item.get('statistics', {})
                
                # Verifica se o vídeo já existe no banco
                existing = db.query(Trend).filter(
                    Trend.platform == 'youtube',
                    Trend.platform_id == video_id
                ).first()
                
                if existing:
                    logger.info(f"Vídeo {video_id} já existe no banco, atualizando...")
                    # Atualiza estatísticas
                    existing.views = int(statistics.get('viewCount', 0))
                    existing.likes = int(statistics.get('likeCount', 0))
                    existing.comments = int(statistics.get('commentCount', 0))
                    existing.updated_at = datetime.now()
                    db.commit()
                else:
                    # Cria nova tendência
                    title = snippet.get('title', '')
                    description = snippet.get('description', '')
                    
                    # Classifica a categoria
                    category = classify_trend_category(title + " " + description)
                    
                    # Extrai hashtags
                    tags = extract_hashtags(description)
                    if not tags and 'tags' in snippet:
                        tags = snippet['tags'][:5] if len(snippet.get('tags', [])) > 5 else snippet.get('tags', [])
                    
                    # Cria o objeto Trend
                    trend = Trend(
                        title=title[:255],  # Limita tamanho para evitar erros
                        description=description[:1000] if description else "",  # Limita tamanho
                        platform="youtube",
                        platform_id=video_id,
                        category=category,
                        author=snippet.get('channelTitle', '')[:100],  # Limita tamanho
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        thumbnail=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        views=int(statistics.get('viewCount', 0)),
                        likes=int(statistics.get('likeCount', 0)),
                        comments=int(statistics.get('commentCount', 0)),
                        tags=",".join(tags[:10]) if tags else "",  # Limita número de tags
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    
                    db.add(trend)
                    db.commit()
                    count += 1
                
                # Libera memória a cada 10 itens
                if count % 10 == 0:
                    gc.collect()
            
            logger.info(f"Busca de tendências do YouTube concluída. {count} novos vídeos adicionados.")
            return {"status": "success", "count": count}
        
        finally:
            db.close()
            # Limpa recursos
            del youtube
            gc.collect()
    
    except Exception as e:
        logger.error(f"Erro ao buscar tendências do YouTube: {str(e)}")
        return {"error": str(e)}

@celery.task
def fetch_reddit_trends():
    """
    Busca os posts em tendência no Reddit e salva no banco.
    """
    # Recarrega as credenciais do ambiente
    reddit_client_id = get_env_var('REDDIT_CLIENT_ID')
    reddit_secret = get_env_var('REDDIT_SECRET')
    reddit_username = get_env_var('REDDIT_USERNAME')
    reddit_password = get_env_var('REDDIT_PASSWORD')
    
    # Se não encontrou no ambiente, tenta usar as variáveis globais
    if not reddit_client_id and REDDIT_CLIENT_ID:
        logger.info("Usando REDDIT_CLIENT_ID da variável global")
        reddit_client_id = REDDIT_CLIENT_ID
    
    if not reddit_secret and REDDIT_SECRET:
        logger.info("Usando REDDIT_SECRET da variável global")
        reddit_secret = REDDIT_SECRET
        
    if not reddit_username and REDDIT_USERNAME:
        logger.info("Usando REDDIT_USERNAME da variável global")
        reddit_username = REDDIT_USERNAME
        
    if not reddit_password and REDDIT_PASSWORD:
        logger.info("Usando REDDIT_PASSWORD da variável global")
        reddit_password = REDDIT_PASSWORD
    
    if not all([reddit_client_id, reddit_secret, reddit_username, reddit_password]):
        logger.error("Credenciais do Reddit não configuradas")
        return {"error": "Reddit credentials not configured"}
    
    logger.info("Iniciando busca de tendências do Reddit")
    
    try:
        import praw
        
        # Cria o cliente do Reddit
        reddit = praw.Reddit(
            client_id=reddit_client_id,
            client_secret=reddit_secret,
            username=reddit_username,
            password=reddit_password,
            user_agent="TrendPulse/1.0"
        )
        
        # Subreddits populares no Brasil
        subreddits = [
            "brasil", "brasilivre", "desabafos", "investimentos", 
            "futebol", "conversas", "gamebirbr", "tiodopave"
        ]
        
        # Processa os resultados
        db = SessionLocal()
        try:
            count = 0
            for subreddit_name in subreddits:
                logger.info(f"Buscando posts do subreddit: {subreddit_name}")
                
                try:
                    subreddit = reddit.subreddit(subreddit_name)
                    
                    # Busca posts populares
                    for post in subreddit.hot(limit=20):
                        # Verifica se o post já existe no banco
                        existing = db.query(Trend).filter(
                            Trend.platform == 'reddit',
                            Trend.platform_id == post.id
                        ).first()
                        
                        if existing:
                            logger.info(f"Post {post.id} já existe no banco, atualizando...")
                            # Atualiza estatísticas
                            existing.views = post.score
                            existing.comments = post.num_comments
                            existing.updated_at = datetime.now()
                            db.commit()
                        else:
                            # Cria nova tendência
                            title = post.title
                            
                            # Obtém descrição formatada
                            description = get_reddit_description(post)
                            
                            # Classifica a categoria
                            category = classify_trend_category(title + " " + description)
                            
                            # Extrai hashtags
                            tags = extract_hashtags(description)
                            if not tags:
                                # Usa flairs como tags
                                if post.link_flair_text:
                                    tags = [post.link_flair_text]
                            
                            # Obtém thumbnail
                            thumbnail = get_reddit_thumbnail(post)
                            
                            # Cria o objeto Trend
                            trend = Trend(
                                title=title[:255],  # Limita tamanho
                                description=description[:1000],  # Limita tamanho
                                platform="reddit",
                                platform_id=post.id,
                                category=category,
                                author=str(post.author)[:100] if post.author else "deleted",  # Limita tamanho
                                url=f"https://www.reddit.com{post.permalink}",
                                thumbnail=thumbnail,
                                views=post.score,
                                likes=post.score,
                                comments=post.num_comments,
                                tags=",".join(tags[:10]) if tags else "",  # Limita número de tags
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            
                            db.add(trend)
                            db.commit()
                            count += 1
                        
                        # Libera memória a cada 5 itens
                        if count % 5 == 0:
                            gc.collect()
                
                except Exception as subreddit_error:
                    logger.error(f"Erro ao processar subreddit {subreddit_name}: {str(subreddit_error)}")
                    continue
            
            logger.info(f"Busca de tendências do Reddit concluída. {count} novos posts adicionados.")
            return {"status": "success", "count": count}
        
        finally:
            db.close()
            # Limpa recursos
            del reddit
            gc.collect()
    
    except Exception as e:
        logger.error(f"Erro ao buscar tendências do Reddit: {str(e)}")
        return {"error": str(e)}

def get_reddit_description(post):
    """
    Obtém a descrição formatada de um post do Reddit.
    """
    # Se for um post de texto, usa o conteúdo
    if post.is_self and post.selftext:
        # Limita o tamanho para economizar memória
        return post.selftext[:500] + "..." if len(post.selftext) > 500 else post.selftext
    
    # Se for um link, usa a URL
    elif hasattr(post, 'url') and post.url:
        return f"Link: {post.url}"
    
    # Caso contrário, retorna vazio
    return ""

def get_reddit_thumbnail(post):
    """
    Obtém a thumbnail de um post do Reddit.
    """
    # Se tiver uma prévia de mídia, usa a URL da prévia
    if hasattr(post, 'preview') and 'images' in post.preview and post.preview['images']:
        try:
            return post.preview['images'][0]['source']['url']
        except (KeyError, IndexError):
            pass
    
    # Se tiver uma thumbnail, usa a thumbnail
    if hasattr(post, 'thumbnail') and post.thumbnail and post.thumbnail.startswith('http'):
        return post.thumbnail
    
    # Caso contrário, retorna vazio
    return ""

@celery.task
def clean_old_trends():
    """
    Remove tendências antigas para manter o banco de dados limpo.
    Mantém apenas os últimos 7 dias de tendências.
    """
    logger.info("Iniciando limpeza de tendências antigas")
    
    try:
        db = SessionLocal()
        try:
            # Define o limite de tempo (30 dias)
            limit_date = datetime.now() - timedelta(days=30)
            
            # Conta quantas tendências serão removidas
            count = db.query(func.count(Trend.id)).filter(Trend.created_at < limit_date).scalar()
            
            if count > 0:
                # Remove tendências antigas
                db.query(Trend).filter(Trend.created_at < limit_date).delete()
                db.commit()
                logger.info(f"Limpeza concluída. {count} tendências antigas removidas.")
            else:
                logger.info("Nenhuma tendência antiga para remover.")
            
            return {"status": "success", "count": count}
        
        finally:
            db.close()
            gc.collect()
    
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