"""
Configurações e fixtures compartilhadas para testes.
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app
from app.models import Base, Trend, get_db, TrendTag, AggregatedContent

# Configuração para testes
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "db+sqlite:///results.sqlite"

# Engine de teste
@pytest.fixture(scope="session")
def test_engine():
    """Cria um engine SQLAlchemy para testes."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    """Cria uma sessão de banco de dados para testes."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture(scope="function")
def client(db_session):
    """Cria um cliente de teste para a API."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def sample_trends(db_session):
    """Cria tendências de exemplo para testes."""
    # Criar tendências
    trends = [
        Trend(
            title="Vídeo de tecnologia",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia",
            views=10000,
            likes=500,
            comments=100,
            published_at=datetime.utcnow()
        ),
        Trend(
            title="Vídeo de entretenimento",
            url="https://youtube.com/video2",
            platform="youtube",
            category="entretenimento",
            views=20000,
            likes=1000,
            comments=200,
            published_at=datetime.utcnow()
        ),
        Trend(
            title="Post de tecnologia",
            url="https://reddit.com/post1",
            platform="reddit",
            category="tecnologia",
            likes=500,
            comments=50,
            published_at=datetime.utcnow()
        ),
        Trend(
            title="Post de entretenimento",
            url="https://reddit.com/post2",
            platform="reddit",
            category="entretenimento",
            likes=1000,
            comments=100,
            published_at=datetime.utcnow()
        ),
    ]
    
    for trend in trends:
        db_session.add(trend)
    db_session.commit()
    
    return trends

@pytest.fixture
def mock_redis(monkeypatch):
    """Mock para o cliente Redis."""
    class MockRedis:
        def __init__(self):
            self.data = {}
            
        def get(self, key):
            return self.data.get(key)
            
        def set(self, key, value, ex=None):
            self.data[key] = value
            
        def delete(self, key):
            if key in self.data:
                del self.data[key]
                
        def exists(self, key):
            return key in self.data
            
        def ping(self):
            return True
    
    mock_instance = MockRedis()
    
    # Atualizar para a estrutura atual do projeto
    from app.check_db import redis_client
    monkeypatch.setattr("app.check_db.redis_client", mock_instance)
    
    return mock_instance

@pytest.fixture
def mock_celery(monkeypatch):
    """Mock para tarefas Celery."""
    class MockAsyncResult:
        def __init__(self, id, status="SUCCESS", result=None):
            self.id = id
            self.status = status
            self._result = result
            
        def get(self):
            return self._result
            
        @property
        def result(self):
            return self._result
    
    class MockTask:
        def __init__(self):
            self.id = "mock-task-id"
            
        def delay(self, *args, **kwargs):
            return MockAsyncResult(self.id)
            
        def apply_async(self, args=None, kwargs=None, **options):
            return MockAsyncResult(self.id)
    
    # Patch para as tarefas específicas conforme necessário
    from app.tasks import fetch_all_trends, cleanup_database
    monkeypatch.setattr(fetch_all_trends, "delay", MockTask().delay)
    monkeypatch.setattr(cleanup_database, "delay", MockTask().delay)
    
    return MockTask() 