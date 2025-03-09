import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import pytest
from app.celery_app import (
    get_redis_broker_url, celery, on_worker_ready, on_beat_init, setup_initial_tasks,
    task_success_handler, task_failure_handler, task_revoked_handler
)

class TestCeleryApp(unittest.TestCase):
    """Testes para as funções do módulo celery_app.py"""

    @patch.dict(os.environ, {}, clear=True)
    def test_get_redis_broker_url_no_env_vars(self):
        """Testa se a função retorna a URL padrão quando não há variáveis de ambiente."""
        url = get_redis_broker_url()
        self.assertEqual(url, 'redis://localhost:6379/0')

    @patch.dict(os.environ, {'CELERY_BROKER_URL': 'redis://test:6379/0'})
    def test_get_redis_broker_url_with_celery_broker_url(self):
        """Testa se a função usa CELERY_BROKER_URL quando disponível."""
        url = get_redis_broker_url()
        self.assertEqual(url, 'redis://test:6379/0')

    @patch.dict(os.environ, {'REDIS_URL': 'redis://redis-url:6379/0'})
    def test_get_redis_broker_url_with_redis_url(self):
        """Testa se a função usa REDIS_URL quando CELERY_BROKER_URL não está disponível."""
        url = get_redis_broker_url()
        self.assertEqual(url, 'memory://')

    @patch.dict(os.environ, {'REDIS_TLS_URL': 'rediss://redis-tls:6379/0'})
    def test_get_redis_broker_url_with_redis_tls_url(self):
        """Testa se a função usa REDIS_TLS_URL quando outras variáveis não estão disponíveis."""
        url = get_redis_broker_url()
        self.assertEqual(url, 'memory://')

    @patch.dict(os.environ, {
        'CELERY_BROKER_URL': 'redis://primary:6379/0',
        'REDIS_URL': 'redis://secondary:6379/0',
        'REDIS_TLS_URL': 'rediss://tertiary:6379/0'
    })
    def test_get_redis_broker_url_priority(self):
        """Testa se a função respeita a prioridade das variáveis de ambiente."""
        url = get_redis_broker_url()
        self.assertEqual(url, 'redis://primary:6379/0')

    @patch('app.celery_app.logger')
    def test_on_worker_ready(self, mock_logger):
        """Testa o callback on_worker_ready."""
        sender = MagicMock()
        with patch('gc.collect') as mock_gc_collect:
            on_worker_ready(sender)
            mock_gc_collect.assert_called_once()
            mock_logger.info.assert_any_call("Worker pronto e conectado ao Redis!")
            mock_logger.info.assert_any_call("Coleta de lixo executada para liberar memória")

    @patch('app.celery_app.logger')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.access')
    def test_on_beat_init_directory_exists_with_permissions(self, mock_access, mock_exists, mock_makedirs, mock_logger):
        """Testa o callback on_beat_init quando o diretório existe e tem permissões."""
        sender = MagicMock()
        mock_exists.return_value = True
        mock_access.return_value = True
        
        on_beat_init(sender)
        
        mock_makedirs.assert_called_once()
        mock_logger.info.assert_any_call("Beat inicializado!")

    @patch('app.celery_app.logger')
    @patch('app.models.SessionLocal')
    @patch('app.models.Trend')
    def test_setup_initial_tasks_with_empty_db(self, mock_trend, mock_session_local, mock_logger):
        """Testa setup_initial_tasks quando o banco de dados está vazio."""
        # Configura o mock para simular banco vazio
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.scalar.return_value = 0
        
        # Configura o mock para a tarefa fetch_all_trends
        with patch('app.tasks.fetch_all_trends') as mock_fetch:
            mock_fetch.delay = MagicMock()
            
            # Executa a função
            setup_initial_tasks(MagicMock())
            
            # Verifica se a tarefa foi chamada
            mock_fetch.delay.assert_called_once()
            mock_logger.info.assert_any_call("Banco de dados vazio. Iniciando busca inicial de tendências...")

    @patch('app.celery_app.logger')
    @patch('app.models.SessionLocal')
    @patch('app.models.Trend')
    def test_setup_initial_tasks_with_data_in_db(self, mock_trend, mock_session_local, mock_logger):
        """Testa setup_initial_tasks quando o banco de dados já contém dados."""
        # Configura o mock para simular banco com dados
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.scalar.return_value = 100
        
        # Configura o mock para a tarefa fetch_all_trends
        with patch('app.tasks.fetch_all_trends') as mock_fetch:
            mock_fetch.delay = MagicMock()
            
            # Executa a função
            setup_initial_tasks(MagicMock())
            
            # Verifica que a tarefa não foi chamada
            mock_fetch.delay.assert_not_called()
            mock_logger.info.assert_any_call("Banco de dados contém 100 tendências. Seguindo agendamento normal.")

    @patch('app.celery_app.logger')
    @patch('app.models.SessionLocal')
    def test_setup_initial_tasks_with_exception(self, mock_session_local, mock_logger):
        """Testa setup_initial_tasks quando ocorre uma exceção."""
        # Configura o mock para lançar uma exceção
        mock_session_local.side_effect = Exception("Erro de conexão")
        
        # Executa a função
        setup_initial_tasks(MagicMock())
        
        # Verifica que o erro foi logado
        mock_logger.error.assert_called_once()
        
    @patch('app.celery_app.logger')
    def test_task_success_handler(self, mock_logger):
        """Testa o handler de sucesso de tarefas."""
        # Cria um mock para o sender
        sender = MagicMock()
        sender.name = "test_task"
        
        # Executa o handler
        task_success_handler(sender=sender)
        
        # Verifica se a mensagem foi logada corretamente
        mock_logger.info.assert_called_once_with("Tarefa test_task concluída com sucesso")
        
    @patch('app.celery_app.logger')
    def test_task_failure_handler(self, mock_logger):
        """Testa o handler de falha de tarefas."""
        # Cria um mock para o sender e a exceção
        sender = MagicMock()
        sender.name = "test_task"
        exception = ValueError("Erro de teste")
        
        # Executa o handler
        task_failure_handler(sender=sender, task_id="123", exception=exception)
        
        # Verifica se a mensagem foi logada corretamente
        mock_logger.error.assert_called_once_with("Tarefa test_task falhou: Erro de teste")
        
    @patch('app.celery_app.logger')
    def test_task_revoked_handler(self, mock_logger):
        """Testa o handler de revogação de tarefas."""
        # Cria um mock para o sender
        sender = MagicMock()
        sender.name = "test_task"
        request = MagicMock()
        
        # Executa o handler
        task_revoked_handler(sender=sender, request=request)
        
        # Verifica se a mensagem foi logada corretamente
        mock_logger.warning.assert_called_once_with("Tarefa test_task foi revogada") 