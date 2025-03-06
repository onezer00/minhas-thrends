"""
Testes unitários para os modelos da aplicação.
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import time

from app.models import Trend, TrendTag

def test_trend_creation(db_session):
    """Testa a criação de uma tendência."""
    # Cria uma tendência
    trend = Trend(
        title="Teste de Tendência",
        description="Descrição de teste",
        platform="youtube",
        external_id="test123",
        category="tecnologia",
        author="Autor Teste",
        views=1000,
        likes=100,
        comments=50,
        url="https://exemplo.com",
        thumbnail="https://exemplo.com/thumb.jpg"
    )
    
    # Adiciona ao banco de dados
    db_session.add(trend)
    db_session.commit()
    
    # Verifica se foi criado com sucesso
    assert trend.id is not None
    assert trend.title == "Teste de Tendência"
    assert trend.platform == "youtube"
    assert trend.created_at is not None
    assert trend.updated_at is not None

def test_trend_unique_constraint(db_session):
    """Testa a restrição de unicidade para platform + external_id."""
    # Cria a primeira tendência
    trend1 = Trend(
        title="Tendência 1",
        description="Descrição 1",
        platform="youtube",
        external_id="unique123",
        category="tecnologia",
        author="Autor 1",
        url="https://exemplo.com/1"
    )
    
    # Adiciona ao banco de dados
    db_session.add(trend1)
    db_session.commit()
    
    # Tenta criar outra tendência com a mesma plataforma e external_id
    trend2 = Trend(
        title="Tendência 2",
        description="Descrição 2",
        platform="youtube",
        external_id="unique123",  # Mesmo external_id
        category="entretenimento",
        author="Autor 2",
        url="https://exemplo.com/2"
    )
    
    # Deve falhar devido à restrição de unicidade
    with pytest.raises(IntegrityError):
        db_session.add(trend2)
        db_session.commit()

def test_trend_tag_relationship(db_session):
    """Testa o relacionamento entre Trend e TrendTag."""
    # Cria uma tendência
    trend = Trend(
        title="Tendência com Tags",
        description="Descrição com tags",
        platform="reddit",
        external_id="tag123",
        category="tecnologia",
        author="Autor Tag",
        url="https://exemplo.com/tag"
    )
    
    # Adiciona ao banco de dados
    db_session.add(trend)
    db_session.commit()
    
    # Adiciona tags
    tag1 = TrendTag(trend_id=trend.id, name="python")
    tag2 = TrendTag(trend_id=trend.id, name="teste")
    
    db_session.add(tag1)
    db_session.add(tag2)
    db_session.commit()
    
    # Busca a tendência com as tags
    result = db_session.query(Trend).filter_by(id=trend.id).first()
    
    # Verifica se as tags foram associadas corretamente
    assert len(result.tags) == 2
    assert "python" in [tag.name for tag in result.tags]
    assert "teste" in [tag.name for tag in result.tags]

def test_trend_default_values(db_session):
    """Testa os valores padrão de uma tendência."""
    # Cria uma tendência com valores mínimos
    trend = Trend(
        title="Tendência Mínima",
        platform="youtube",
        external_id="min123",
        url="https://exemplo.com/min"
    )
    
    # Adiciona ao banco de dados
    db_session.add(trend)
    db_session.commit()
    
    # Verifica os valores padrão
    assert trend.description is None  # description pode ser None
    assert trend.category is None
    assert trend.views == 0
    assert trend.likes == 0
    assert trend.comments == 0
    assert trend.created_at is not None
    assert trend.updated_at is not None

def test_trend_timestamps(db_session):
    """Testa os timestamps de criação e atualização."""
    # Cria uma tendência
    trend = Trend(
        title="Tendência Timestamp",
        platform="youtube",
        external_id="time123",
        url="https://exemplo.com/time"
    )
    
    # Adiciona ao banco de dados
    db_session.add(trend)
    db_session.commit()
    
    # Verifica se os timestamps foram definidos
    assert isinstance(trend.created_at, datetime)
    assert isinstance(trend.updated_at, datetime)
    
    # Armazena o timestamp de atualização original
    original_updated_at = trend.updated_at
    
    # Adiciona um pequeno atraso para garantir que o timestamp seja diferente
    time.sleep(0.1)

    # Atualiza a tendência
    trend.title = "Tendência Timestamp Atualizada"
    db_session.commit()
    
    # Verifica se o timestamp de atualização foi modificado
    assert trend.updated_at > original_updated_at 