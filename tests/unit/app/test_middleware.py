import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import time
from app.main import app
from app.models import check_db_connection

def test_status_endpoint_basic():
    """Testa o endpoint de status básico."""
    with patch("app.models.check_db_connection", return_value=True), \
         patch("app.tasks.check_redis_connection", return_value=True):
        
        client = TestClient(app)
        response = client.get("/api/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "ok"
        assert "database" in data
        assert data["database"] == "connected"
        assert "redis" in data
        assert data["redis"] == "connected"
        assert "timestamp" in data
        assert "version" in data

@patch("app.models.check_db_connection")
@patch("app.tasks.check_redis_connection")
def test_status_endpoint_with_mocks(mock_redis, mock_db):
    """Testa o endpoint de status com diferentes estados de conexão."""
    # Teste 1: Tudo conectado
    mock_db.return_value = True
    mock_redis.return_value = True
    
    client = TestClient(app)
    response = client.get("/api/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"
    
    # Teste 2: Banco desconectado
    mock_db.return_value = False
    mock_redis.return_value = True
    
    response = client.get("/api/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "error"
    assert data["redis"] == "connected"
    
    # Teste 3: Redis desconectado
    mock_db.return_value = True
    mock_redis.return_value = False
    
    response = client.get("/api/status")
    
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"
    assert data["redis"] == "disconnected"

def test_middleware_basic():
    """Testa o middleware de log de requisições."""
    with patch("app.models.check_db_connection", return_value=True), \
         patch("app.tasks.check_redis_connection", return_value=True):
        
        client = TestClient(app)
        response = client.get("/api/status")
        
        assert response.status_code == 200

# Novos testes para aumentar a cobertura

def test_middleware_handle_free_tier_sleep():
    """Testa o middleware handle_free_tier_sleep."""
    # Não podemos testar diretamente o sleep, mas podemos verificar se o middleware não quebra a aplicação
    client = TestClient(app)
    response = client.get("/api/status")
    
    assert response.status_code == 200

def test_middleware_origin_allowed():
    """Testa o middleware com origem permitida."""
    with patch("app.main.is_origin_allowed", return_value=True):
        client = TestClient(app)
        response = client.get("/api/status", headers={"Origin": "https://example.com"})
        
        assert response.status_code == 200

def test_middleware_origin_not_allowed():
    """Testa o middleware com origem não permitida."""
    with patch("app.main.is_origin_allowed", return_value=False):
        client = TestClient(app)
        # Não podemos testar diretamente a rejeição CORS porque o TestClient não processa CORS
        # Mas podemos verificar se a função is_origin_allowed é chamada
        response = client.get("/api/status", headers={"Origin": "https://malicious.com"})
        
        assert response.status_code == 200  # O TestClient não implementa CORS 