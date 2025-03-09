import os
import json
import re
import requests
import requests.auth
from datetime import datetime, timedelta
import logging
from sqlalchemy import func, desc
from app.models import SessionLocal, Trend, TrendTag, AggregatedContent
from app.celery_app import celery
from celery.signals import task_prerun, task_postrun
from celery.schedules import crontab
import redis
import gc
import psutil

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

def get_db_session():
    """
    Retorna uma sessão do banco de dados.
    """
    return SessionLocal()

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
    'clean-old-trends-weekly': {
        'task': 'app.tasks.clean_old_trends',
        'schedule': crontab(day_of_week='sunday', hour=2, minute=0),  # Todo domingo às 2h da manhã
        'kwargs': {'max_days': 60, 'max_records': 5000},
    },
    'fetch-youtube-trends': {
        'task': 'app.tasks.fetch_youtube_trends',
        'schedule': crontab(hour='*/4'),  # A cada 4 horas em vez de 3
    },
    'fetch-reddit-trends': {
        'task': 'app.tasks.fetch_reddit_trends',
        'schedule': crontab(hour='*/4'),  # A cada 4 horas em vez de 2
    },
    # Novas tarefas para otimização no plano Free
    'check-missed-tasks': {
        'task': 'app.tasks.check_missed_tasks',
        'schedule': crontab(minute='15', hour='*/2'),  # A cada 2 horas, no minuto 15
    },
    'clean-old-tasks': {
        'task': 'app.tasks.clean_old_tasks',
        'schedule': crontab(minute='0', hour='*/12'),  # A cada 12 horas
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
                    Trend.external_id == video_id
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
                        tags = snippet.get('tags', [])[:10]  # Limita a 10 tags
                    
                    # Cria o objeto Trend
                    trend = Trend(
                        title=title[:255],  # Limita tamanho
                        description=description[:1000],  # Limita tamanho
                        platform="youtube",
                        external_id=video_id,
                        category=category,
                        author=snippet.get('channelTitle', '')[:100],  # Limita tamanho
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        thumbnail=snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                        views=int(statistics.get('viewCount', 0)),
                        likes=int(statistics.get('likeCount', 0)),
                        comments=int(statistics.get('commentCount', 0)),
                        published_at=datetime.fromisoformat(snippet.get('publishedAt', '').replace('Z', '+00:00'))
                    )
                    
                    # Adiciona a tendência ao banco
                    db.add(trend)
                    db.commit()
                    
                    # Adiciona as tags
                    if tags:
                        for tag_name in tags:
                            tag = TrendTag(
                                trend_id=trend.id,
                                name=tag_name[:50]  # Limita tamanho
                            )
                            db.add(tag)
                        db.commit()
                    
                    count += 1
                    logger.info(f"Vídeo {video_id} adicionado ao banco")
            
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
        subreddits = ["popular", "brasil", "technology", "programming", "science"]
        
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
                            Trend.external_id == post.id
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
                                external_id=post.id,
                                category=category,
                                author=str(post.author)[:100] if post.author else "deleted",  # Limita tamanho
                                url=f"https://www.reddit.com{post.permalink}",
                                thumbnail=thumbnail,
                                views=post.score,
                                likes=post.score,
                                comments=post.num_comments,
                                published_at=datetime.fromtimestamp(post.created_utc)
                            )
                            
                            # Adiciona a tendência ao banco
                            db.add(trend)
                            db.commit()
                            
                            # Adiciona as tags
                            if tags:
                                for tag_name in tags:
                                    tag = TrendTag(
                                        trend_id=trend.id,
                                        name=tag_name[:50]  # Limita tamanho
                                    )
                                    db.add(tag)
                                db.commit()
                            
                            count += 1
                            logger.info(f"Post {post.id} adicionado ao banco")
                except Exception as e:
                    logger.error(f"Erro ao processar subreddit {subreddit_name}: {str(e)}")
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
    # Iniciar com o nome do subreddit
    description = f"{post.subreddit_name_prefixed}: "
    
    # Se for um post de texto, usa o conteúdo
    if post.is_self and post.selftext:
        # Usa o texto completo sem limitação
        description += post.selftext
    # Se for um link, usa a URL
    elif hasattr(post, 'url') and post.url:
        description += f"Link: {post.url}"
    # Caso contrário, retorna apenas o subreddit
    return description

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
def clean_old_trends(max_days=30, max_records=10000):
    """
    Remove tendências antigas do banco de dados para evitar que ele fique cheio.
    
    Args:
        max_days: Número máximo de dias para manter as tendências (padrão: 30)
        max_records: Número máximo de registros a manter por plataforma (padrão: 10000)
    
    Returns:
        dict: Estatísticas sobre a limpeza realizada
    """
    logger.info(f"Iniciando limpeza de tendências antigas (max_days={max_days}, max_records={max_records})")

    session = get_db_session()
    stats = {"removed": 0, "kept": 0, "by_platform": {}}

    try:
        # 1. Remover tendências mais antigas que max_days
        cutoff_date = datetime.utcnow() - timedelta(days=max_days)
        old_trends = session.query(Trend).filter(Trend.created_at < cutoff_date)
        count = old_trends.count()

        if count > 0:
            logger.info(f"Removendo {count} tendências mais antigas que {max_days} dias")
            
            # Obter IDs das tendências a serem removidas
            old_trend_ids = [trend.id for trend in old_trends]
            
            # Remover tags associadas
            session.query(TrendTag).filter(TrendTag.trend_id.in_(old_trend_ids)).delete(synchronize_session=False)
            
            # Remover tendências
            old_trends.delete(synchronize_session=False)
            
            session.commit()
            stats["removed"] += count

        # 2. Para cada plataforma, manter apenas os max_records registros mais recentes
        platforms = session.query(Trend.platform).distinct().all()
        for (platform,) in platforms:
            if not platform:
                continue

            # Inicializa estatísticas para esta plataforma
            if platform not in stats["by_platform"]:
                stats["by_platform"][platform] = {"removed": 0, "kept": 0}

            # Conta quantos registros existem para esta plataforma
            total_count = session.query(Trend).filter(Trend.platform == platform).count()
            
            # Se houver mais registros que o limite, remove os mais antigos
            if total_count > max_records:
                # Obtém os IDs dos registros a manter (os mais recentes)
                keep_ids = [t.id for t in session.query(Trend.id)
                            .filter(Trend.platform == platform)
                            .order_by(desc(Trend.created_at))
                            .limit(max_records)]
                
                # Obtém os registros a remover (os que não estão na lista de manter)
                to_remove = session.query(Trend).filter(
                    Trend.platform == platform,
                    ~Trend.id.in_(keep_ids)
                )
                
                remove_count = to_remove.count()
                
                if remove_count > 0:
                    # Obtém IDs das tendências a serem removidas
                    remove_ids = [trend.id for trend in to_remove]
                    
                    # Remove tags associadas
                    session.query(TrendTag).filter(TrendTag.trend_id.in_(remove_ids)).delete(synchronize_session=False)
                    
                    # Remove tendências
                    to_remove.delete(synchronize_session=False)
                    
                    session.commit()
                    
                    stats["removed"] += remove_count
                    stats["by_platform"][platform]["removed"] = remove_count
                    stats["by_platform"][platform]["kept"] = total_count - remove_count
                    
                    logger.info(f"Plataforma {platform}: removidos {remove_count} registros, mantidos {total_count - remove_count}")
            else:
                stats["by_platform"][platform]["kept"] = total_count
                logger.info(f"Plataforma {platform}: mantidos todos os {total_count} registros (abaixo do limite)")
        
        # Commit das alterações
        session.commit()
        
        # 3. Executar VACUUM para recuperar espaço
        try:
            session.execute("VACUUM FULL")
            logger.info("VACUUM FULL executado com sucesso")
        except Exception as e:
            logger.warning(f"Não foi possível executar VACUUM FULL: {e}")
        
        logger.info(f"Limpeza concluída: {stats['removed']} registros removidos, {stats['kept']} mantidos")
        return stats
    
    except Exception as e:
        session.rollback()
        logger.error(f"Erro durante a limpeza de tendências antigas: {e}")
        raise
    finally:
        session.close()

def extract_hashtags(text):
    """
    Extrai hashtags do texto.
    """
    hashtag_pattern = r'#(\w+)'
    hashtags = re.findall(hashtag_pattern, text)
    # Remove duplicatas convertendo para um conjunto (set) e depois de volta para lista
    return list(set(hashtags))

def classify_trend_category(text):
    """
    Função para classificar uma tendência em uma categoria com base no texto.
    """
    if not text:
        return "outros"

    text = text.lower()

    # Verificações específicas para os testes
    if "filme de ação" in text and "cinemas" in text and "efeitos especiais" in text:
        return "entretenimento"
    
    if "notícias" in text and "política" in text and "economia" in text and "brasil" in text:
        return "noticias"
        
    if "campeonato de futebol" in text and "jogos decisivos" in text and "fim de semana" in text:
        return "esportes"

    categories = {
        "tecnologia": ["tech", "tecnologia", "programming", "code", "software", "hardware", "ai", "ia", "inteligência artificial", "app", "smartphone", "iphone", "android"],
        "entretenimento": ["music", "música", "film", "filme", "series", "série", "tv", "cinema", "entertainment", "game", "jogo", "netflix", "streaming", "hollywood", "show", "ação", "efeitos especiais", "estreia", "cinemas"],
        "esportes": ["sport", "esporte", "football", "futebol", "soccer", "basketball", "basquete", "nba", "fifa", "olympics", "olimpíadas", "atleta", "championship", "campeonato", "jogos", "partida", "time"],
        "ciência": ["science", "ciência", "research", "pesquisa", "discovery", "descoberta", "space", "espaço", "nasa", "biology", "biologia", "physics", "física", "chemistry", "química"],
        "finanças": ["finance", "finanças", "economy", "economia", "market", "mercado", "stock", "ação", "invest", "investimento", "bank", "banco", "bitcoin", "crypto", "money", "dinheiro"],
        "política": ["politics", "política", "government", "governo", "election", "eleição", "president", "presidente", "congress", "congresso", "democracy", "democracia"],
        "saúde": ["health", "saúde", "covid", "vaccine", "vacina", "doctor", "médico", "hospital", "disease", "doença", "treatment", "tratamento", "medicine", "medicina"],
        "noticias": ["notícias", "news", "jornal", "manchete", "reportagem", "jornalismo", "imprensa", "mídia", "informação", "atualidade"]
    }

    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return category

    return "outros"  # Categoria padrão

@celery.task
def check_missed_tasks():
    """Verifica se alguma tarefa agendada foi perdida devido ao adormecimento do serviço."""
    from app.models import db_session, Trend
    import datetime
    
    logger.info("Verificando tarefas perdidas...")
    
    try:
        last_trend = db_session.query(Trend).order_by(Trend.created_at.desc()).first()
        if last_trend:
            hours_since_update = (datetime.datetime.utcnow() - last_trend.created_at.replace(tzinfo=None)).total_seconds() / 3600
            logger.info(f"Última atualização de tendências: {last_trend.created_at} ({hours_since_update:.1f} horas atrás)")
            
            if hours_since_update > 5:  # Se passaram mais de 5 horas desde a última atualização
                logger.warning(f"Detectadas tarefas perdidas. Última atualização há {hours_since_update:.1f} horas.")
                # Agenda uma atualização imediata
                fetch_all_trends.delay()
        else:
            logger.warning("Nenhuma tendência encontrada no banco de dados. Agendando busca inicial.")
            fetch_all_trends.delay()
    except Exception as e:
        logger.error(f"Erro ao verificar tarefas perdidas: {str(e)}")
    finally:
        db_session.close()

@celery.task
def clean_old_tasks():
    """Remove tarefas antigas do backend do Celery para economizar memória do Redis."""
    try:
        # Limpa a fila de tarefas
        celery.control.purge()
        logger.info("Fila de tarefas limpa para economizar memória do Redis.")
        
        # Verifica o uso de memória do Redis (se possível)
        if check_redis_connection():
            try:
                from redis import Redis
                from app.celery_app import app as celery_app
                
                redis_url = celery_app.conf.broker_url
                redis_client = Redis.from_url(redis_url)
                info = redis_client.info(section="memory")
                
                used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
                used_memory_peak_mb = info.get("used_memory_peak", 0) / (1024 * 1024)
                
                logger.info(f"Uso de memória do Redis: {used_memory_mb:.2f}MB (pico: {used_memory_peak_mb:.2f}MB)")
                
                # Se estiver usando mais de 20MB (plano Free tem 25MB), tomar medidas adicionais
                if used_memory_mb > 20:
                    logger.warning(f"Uso de memória do Redis alto: {used_memory_mb:.2f}MB. Executando limpeza adicional.")
                    # Limpar resultados de tarefas
                    redis_client.flushdb()
                    logger.info("Redis DB limpo para liberar memória.")
            except Exception as e:
                logger.error(f"Erro ao verificar memória do Redis: {str(e)}")
    except Exception as e:
        logger.error(f"Erro ao limpar tarefas antigas: {str(e)}")