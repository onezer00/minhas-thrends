"""
Testes unitários para as funções de busca de tendências.
"""
import unittest
from unittest.mock import patch, MagicMock
import pytest
from datetime import datetime

from app.tasks import fetch_youtube_trends, fetch_reddit_trends
from app.models import Trend

pytestmark = pytest.mark.unit

class TestYouTubeTrendFetcher(unittest.TestCase):
    """Testes para o fetcher de tendências do YouTube."""
    
    @patch('app.tasks.SessionLocal')
    @patch('googleapiclient.discovery.build')
    def test_fetch_youtube_trends_success(self, mock_build, mock_session_local):
        """Testa a busca de tendências do YouTube com sucesso."""
        # Configurar o mock da sessão do banco de dados
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Configurar o mock do serviço YouTube
        mock_youtube = MagicMock()
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()
        
        # Configurar a resposta da API
        mock_execute.return_value = {
            'items': [
                {
                    'id': 'video1',
                    'snippet': {
                        'title': 'Vídeo de Tecnologia #tech',
                        'description': 'Descrição do vídeo #tecnologia',
                        'publishedAt': '2023-01-01T00:00:00Z',
                        'channelTitle': 'Canal de Tech',
                        'thumbnails': {
                            'high': {
                                'url': 'https://example.com/thumbnail.jpg'
                            }
                        }
                    },
                    'statistics': {
                        'viewCount': '1000',
                        'likeCount': '100',
                        'commentCount': '10'
                    }
                }
            ]
        }
        
        # Configurar a cadeia de chamadas
        mock_list.execute = mock_execute
        mock_videos.list.return_value = mock_list
        mock_youtube.videos.return_value = mock_videos
        mock_build.return_value = mock_youtube
        
        # Configurar o mock para simular que o vídeo não existe no banco
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = None
        mock_filter.return_value.first = mock_first
        mock_query.filter = mock_filter
        mock_session.query.return_value = mock_query
        
        # Executar a função
        result = fetch_youtube_trends()
        
        # Verificar se a API foi chamada corretamente
        mock_build.assert_called_once()
        
        # Verificar se os dados foram salvos no banco de dados
        self.assertTrue(mock_session.add.called)
        self.assertTrue(mock_session.commit.called)
    
    @patch('app.tasks.SessionLocal')
    @patch('googleapiclient.discovery.build')
    def test_fetch_youtube_trends_error(self, mock_build, mock_session_local):
        """Testa a busca de tendências do YouTube com erro."""
        # Simular um erro na API
        mock_build.side_effect = Exception("API Error")
        
        # Executar a função
        result = fetch_youtube_trends()
        
        # Verificar se a API foi chamada
        mock_build.assert_called_once()
        
        # Verificar que nenhum dado foi salvo no banco de dados
        mock_session_local.assert_not_called()
    
    @patch('app.tasks.SessionLocal')
    @patch('googleapiclient.discovery.build')
    def test_fetch_youtube_trends_empty(self, mock_build, mock_session_local):
        """Testa a busca de tendências do YouTube com resposta vazia."""
        # Configurar o mock da sessão do banco de dados
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Configurar o mock do serviço YouTube com resposta vazia
        mock_youtube = MagicMock()
        mock_videos = MagicMock()
        mock_list = MagicMock()
        mock_execute = MagicMock()
        
        # Configurar a resposta vazia da API
        mock_execute.return_value = {'items': []}
        
        # Configurar a cadeia de chamadas
        mock_list.execute = mock_execute
        mock_videos.list = MagicMock(return_value=mock_list)
        mock_youtube.videos = mock_videos
        mock_build.return_value = mock_youtube
        
        # Executar a função
        result = fetch_youtube_trends()
        
        # Verificar se a API foi chamada corretamente
        mock_build.assert_called_once()
        
        # Verificar que nenhum dado foi salvo no banco de dados
        self.assertFalse(mock_session.add.called)

class TestRedditTrendFetcher(unittest.TestCase):
    """Testes para o fetcher de tendências do Reddit."""
    
    @patch('app.tasks.SessionLocal')
    @patch('praw.Reddit')
    def test_fetch_reddit_trends_success(self, mock_reddit_class, mock_session_local):
        """Testa a busca de tendências do Reddit com sucesso."""
        # Configurar o mock da sessão do banco de dados
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Configurar o mock do cliente Reddit
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        
        # Configurar a resposta da API
        mock_post = MagicMock()
        mock_post.id = 'post1'
        mock_post.title = "Post de Tecnologia #tech"
        mock_post.selftext = "Conteúdo do post #tecnologia"
        mock_post.created_utc = 1672531200  # 2023-01-01 00:00:00 UTC
        mock_post.author = "RedditUser"
        mock_post.url = "https://www.reddit.com/r/brasil/comments/123456/post_title"
        mock_post.permalink = "/r/brasil/comments/123456/post_title"
        mock_post.score = 100
        mock_post.num_comments = 10
        mock_post.link_flair_text = "Tecnologia"
        
        # Configurar a cadeia de chamadas
        mock_subreddit.hot.return_value = [mock_post]
        mock_reddit.subreddit.return_value = mock_subreddit
        mock_reddit_class.return_value = mock_reddit
        
        # Configurar o mock para simular que o post não existe no banco
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_first = MagicMock()
        mock_first.return_value = None
        mock_filter.return_value.first = mock_first
        mock_query.filter = mock_filter
        mock_session.query.return_value = mock_query
        
        # Executar a função
        result = fetch_reddit_trends()
        
        # Verificar se o cliente Reddit foi criado corretamente
        mock_reddit_class.assert_called_once()
        
        # Verificar se os dados foram salvos no banco de dados
        self.assertTrue(mock_session.add.called)
        self.assertTrue(mock_session.commit.called)
    
    @patch('app.tasks.SessionLocal')
    @patch('praw.Reddit')
    def test_fetch_reddit_trends_error(self, mock_reddit_class, mock_session_local):
        """Testa a busca de tendências do Reddit com erro."""
        # Simular um erro na API
        mock_reddit_class.side_effect = Exception("API Error")
        
        # Executar a função
        result = fetch_reddit_trends()
        
        # Verificar se o cliente Reddit foi criado
        mock_reddit_class.assert_called_once()
        
        # Verificar que nenhum dado foi salvo no banco de dados
        mock_session_local.assert_not_called()
    
    @patch('app.tasks.SessionLocal')
    @patch('praw.Reddit')
    def test_fetch_reddit_trends_empty(self, mock_reddit_class, mock_session_local):
        """Testa a busca de tendências do Reddit com resposta vazia."""
        # Configurar o mock da sessão do banco de dados
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        
        # Configurar o mock do cliente Reddit com resposta vazia
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        
        # Configurar a resposta vazia da API
        mock_subreddit.hot.return_value = []
        mock_reddit.subreddit.return_value = mock_subreddit
        mock_reddit_class.return_value = mock_reddit
        
        # Executar a função
        result = fetch_reddit_trends()
        
        # Verificar se o cliente Reddit foi criado corretamente
        mock_reddit_class.assert_called_once()
        
        # Verificar que nenhum dado foi salvo no banco de dados
        self.assertFalse(mock_session.add.called) 