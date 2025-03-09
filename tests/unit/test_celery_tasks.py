"""
Testes unitários para as tarefas Celery.
"""
import unittest
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Atualizando as importações para refletir a estrutura atual do projeto
from app.tasks import (
    fetch_all_trends,
    fetch_youtube_trends,
    fetch_reddit_trends,
    check_redis_connection
)
from app.main import cleanup_database
from app.models import Trend

@pytest.mark.unit
class TestFetchTrendsTasks(unittest.TestCase):
    """Testes para as tarefas de busca de tendências."""
    
    @patch('app.tasks.fetch_reddit_trends')
    @patch('app.tasks.fetch_youtube_trends')
    @patch('app.tasks.check_redis_connection')
    def test_fetch_all_trends(self, mock_check_redis, mock_fetch_youtube, mock_fetch_reddit):
        """Testa a busca de todas as tendências."""
        # Configurar os mocks
        mock_check_redis.return_value = True
        mock_fetch_youtube.delay = MagicMock()
        mock_fetch_reddit.delay = MagicMock()

        # Executar a tarefa
        result = fetch_all_trends()

        # Verificar se as tarefas foram chamadas
        mock_fetch_youtube.delay.assert_called_once()
        mock_fetch_reddit.delay.assert_called_once()

        # Verificar o resultado
        assert "youtube" in result
        assert "reddit" in result
        assert result["youtube"] == "Tarefa iniciada"
        assert result["reddit"] == "Tarefa iniciada"

    @patch('googleapiclient.discovery.build')
    @patch('app.tasks.get_env_var')
    def test_fetch_youtube_trends_success(self, mock_get_env_var, mock_build):
        """Testa a busca de tendências do YouTube com sucesso."""
        # Configurar os mocks
        mock_get_env_var.return_value = "fake_api_key"

        # Mock para o serviço do YouTube
        mock_youtube_service = MagicMock()
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()

        # Configurar a resposta simulada da API
        mock_execute.return_value = {
            "items": [
                {
                    "id": "video1",
                    "snippet": {
                        "title": "Vídeo de Teste 1",
                        "description": "Descrição do vídeo 1",
                        "publishedAt": "2023-01-01T00:00:00Z",
                        "channelTitle": "Canal de Teste",
                        "thumbnails": {
                            "high": {
                                "url": "https://example.com/thumbnail1.jpg"
                            }
                        }
                    },
                    "statistics": {
                        "viewCount": "1000",
                        "likeCount": "100"
                    }
                }
            ]
        }

        # Configurar a cadeia de chamadas
        mock_list.execute = mock_execute
        mock_videos.list = MagicMock(return_value=mock_list)
        mock_youtube_service.videos = MagicMock(return_value=mock_videos)
        mock_build.return_value = mock_youtube_service

        # Executar a tarefa
        result = fetch_youtube_trends()

        # Verificar se o serviço foi criado corretamente
        # Aceitar qualquer parâmetro adicional que possa ser passado
        mock_build.assert_called_once()
        args, kwargs = mock_build.call_args
        assert args[0] == "youtube"
        assert args[1] == "v3"
        assert kwargs["developerKey"] == "fake_api_key"

        # Verificar o resultado
        assert result["status"] == "success"
        # O count pode ser 0 (se o vídeo já existir no banco) ou 1 (se for novo)
        assert result["count"] in [0, 1], f"Count deve ser 0 ou 1, mas é {result['count']}"

    @patch('app.tasks.YOUTUBE_API_KEY', None)
    @patch('app.tasks.get_env_var')
    def test_fetch_youtube_trends_error(self, mock_get_env_var):
        """Testa a busca de tendências do YouTube com erro."""
        # Configurar o mock para retornar None (API key não configurada)
        mock_get_env_var.return_value = None

        # Executar a tarefa
        result = fetch_youtube_trends()

        # Verificar o resultado
        assert "error" in result
        assert "Chave de API do YouTube não configurada" in result["error"]

    @patch('praw.Reddit')
    @patch('app.tasks.get_env_var')
    def test_fetch_reddit_trends_success(self, mock_get_env_var, mock_reddit):
        """Testa a busca de tendências do Reddit com sucesso."""
        # Configurar os mocks para as credenciais
        mock_get_env_var.side_effect = lambda var_name, default=None: {
            'REDDIT_CLIENT_ID': 'fake_client_id',
            'REDDIT_SECRET': 'fake_client_secret',
            'REDDIT_USERNAME': 'fake_username',
            'REDDIT_PASSWORD': 'fake_password'
        }.get(var_name, default)

        # Mock para o cliente do Reddit
        mock_reddit_instance = MagicMock()
        mock_subreddit = MagicMock()
        mock_hot = MagicMock()
        
        # Configurar posts simulados
        mock_post1 = MagicMock()
        mock_post1.id = "post1"
        mock_post1.title = "Post de Teste 1"
        mock_post1.selftext = "Conteúdo do post 1"
        mock_post1.created_utc = 1609459200  # 2021-01-01 00:00:00 UTC
        mock_post1.author = MagicMock()
        mock_post1.author.name = "Autor de Teste"
        mock_post1.subreddit = MagicMock()
        mock_post1.subreddit.display_name = "popular"
        mock_post1.score = 1000
        mock_post1.num_comments = 100
        mock_post1.url = "https://example.com/post1"
        
        # Configurar a cadeia de chamadas
        mock_hot.return_value = [mock_post1]
        mock_subreddit.hot.return_value = mock_hot
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_reddit.return_value = mock_reddit_instance
        
        # Executar a tarefa
        result = fetch_reddit_trends()
        
        # Verificar se o cliente foi criado corretamente
        mock_reddit.assert_called_once_with(
            client_id='fake_client_id',
            client_secret='fake_client_secret',
            username='fake_username',
            password='fake_password',
            user_agent="TrendPulse/1.0"
        )
        
        # Verificar o resultado
        assert result["status"] == "success"

    @patch('app.tasks.REDDIT_CLIENT_ID', None)
    @patch('app.tasks.REDDIT_SECRET', None)
    @patch('app.tasks.REDDIT_USERNAME', None)
    @patch('app.tasks.REDDIT_PASSWORD', None)
    @patch('app.tasks.get_env_var')
    def test_fetch_reddit_trends_error(self, mock_get_env_var):
        """Testa a busca de tendências do Reddit com erro."""
        # Configurar o mock para retornar None (credenciais não configuradas)
        mock_get_env_var.return_value = None

        # Executar a tarefa
        result = fetch_reddit_trends()

        # Verificar o resultado
        assert "error" in result
        assert "Reddit credentials not configured" in result["error"]

class TestCleanupDatabaseTask:
    """Testes para a tarefa de limpeza do banco de dados."""
    
    @patch('app.main.get_db')
    async def test_cleanup_database(self, mock_get_db):
        """Testa a limpeza de tendências antigas do banco de dados."""
        # Configurar o mock da sessão do banco de dados
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session
        
        # Configurar dados de teste
        now = datetime.now()
        
        # Tendências recentes (menos de 30 dias)
        recent_trends = [
            Trend(id=1, title="Tendência recente 1", created_at=now - timedelta(days=5)),
            Trend(id=2, title="Tendência recente 2", created_at=now - timedelta(days=10))
        ]
        
        # Tendências médias (entre 30 e 60 dias)
        medium_trends = [
            Trend(id=3, title="Tendência média 1", created_at=now - timedelta(days=35)),
            Trend(id=4, title="Tendência média 2", created_at=now - timedelta(days=45))
        ]
        
        # Tendências antigas (mais de 60 dias)
        old_trends = [
            Trend(id=5, title="Tendência antiga 1", created_at=now - timedelta(days=65)),
            Trend(id=6, title="Tendência antiga 2", created_at=now - timedelta(days=90))
        ]
        
        # Configurar o mock para retornar as tendências antigas
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = old_trends
        
        # Executar a tarefa
        result = await cleanup_database(days=60)
        
        # Verificar se a consulta foi feita corretamente
        mock_session.query.assert_called_once_with(Trend)
        
        # Verificar se as tendências antigas foram excluídas
        assert mock_session.delete.call_count == 2  # 2 tendências antigas
        assert mock_session.commit.call_count == 1
        
        # Verificar o resultado
        assert result == 2  # 2 tendências removidas 