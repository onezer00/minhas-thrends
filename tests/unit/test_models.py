"""
Testes unitários para os modelos de dados.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

# Atualizando as importações para refletir a estrutura atual do projeto
from app.models import Trend, TrendTag, AggregatedContent

pytestmark = pytest.mark.unit

class TestTrendModel:
    """Testes para o modelo Trend."""
    
    def test_create_trend(self, db_session):
        """Testa a criação de uma tendência."""
        # Criar uma tendência
        trend = Trend(
            title="Vídeo de teste",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia",
            views=10000,
            likes=500,
            comments=100,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            published_at=datetime.now()
        )
        
        db_session.add(trend)
        db_session.commit()
        
        # Verificar se a tendência foi criada
        assert trend.id is not None
        assert trend.title == "Vídeo de teste"
        assert trend.url == "https://youtube.com/video1"
        assert trend.platform == "youtube"
        assert trend.category == "tecnologia"
        assert trend.views == 10000
        assert trend.likes == 500
        assert trend.comments == 100
        assert trend.created_at is not None
        assert trend.updated_at is not None
        assert trend.published_at is not None
    
    def test_trend_to_dict(self, db_session):
        """Testa o método to_dict do modelo Trend."""
        # Criar uma tendência
        trend = Trend(
            title="Vídeo de teste",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia",
            views=10000,
            likes=500,
            comments=100,
            published_at=datetime.now()
        )
        
        db_session.add(trend)
        db_session.commit()
        
        # Criar tags para a tendência
        tag1 = TrendTag(trend_id=trend.id, name="python")
        tag2 = TrendTag(trend_id=trend.id, name="programação")
        db_session.add_all([tag1, tag2])
        db_session.commit()
        
        # Verificar o método to_dict
        trend_dict = trend.to_dict()
        assert trend_dict["id"] == trend.id
        assert trend_dict["title"] == "Vídeo de teste"
        assert trend_dict["url"] == "https://youtube.com/video1"
        assert trend_dict["platform"] == "youtube"
        assert trend_dict["category"] == "tecnologia"
        assert trend_dict["views"] == "10.000"
        assert trend_dict["likes"] == 500
        assert trend_dict["comments"] == 100
        assert "timeAgo" in trend_dict
        assert "tags" in trend_dict
        assert len(trend_dict["tags"]) == 2
        assert "python" in trend_dict["tags"]
        assert "programação" in trend_dict["tags"]
    
    def test_trend_time_ago(self, db_session):
        """Testa o cálculo de tempo decorrido."""
        now = datetime.now()

        # Tendência de agora
        trend_now = Trend(
            title="Tendência recente",
            platform="youtube",
            published_at=now
        )

        # Tendência de 30 minutos atrás
        trend_minutes = Trend(
            title="Tendência de minutos",
            platform="youtube",
            published_at=now - timedelta(minutes=30)
        )

        # Tendência de 3 horas atrás
        trend_hours = Trend(
            title="Tendência de horas",
            platform="youtube",
            published_at=now - timedelta(hours=3)
        )

        # Tendência de 5 dias atrás
        trend_days = Trend(
            title="Tendência de dias",
            platform="youtube",
            published_at=now - timedelta(days=5)
        )

        # Tendência de 2 meses atrás
        trend_months = Trend(
            title="Tendência de meses",
            platform="youtube",
            published_at=now - timedelta(days=60)
        )

        # Tendência de 2 anos atrás
        trend_years = Trend(
            title="Tendência de anos",
            platform="youtube",
            published_at=now - timedelta(days=730)
        )

        db_session.add_all([trend_now, trend_minutes, trend_hours, trend_days, trend_months, trend_years])

        db_session.commit()

        # Verificar o cálculo de tempo - verificamos apenas se existe um valor para timeAgo
        assert "timeAgo" in trend_minutes.to_dict()
        assert "timeAgo" in trend_hours.to_dict()
        assert "timeAgo" in trend_days.to_dict()
        assert "timeAgo" in trend_months.to_dict()
        assert "timeAgo" in trend_years.to_dict()
        
        # Verificar se os valores não estão vazios
        assert trend_minutes.to_dict()["timeAgo"] != ""
        assert trend_hours.to_dict()["timeAgo"] != ""
        assert trend_days.to_dict()["timeAgo"] != ""
        assert trend_months.to_dict()["timeAgo"] != ""
        assert trend_years.to_dict()["timeAgo"] != ""

class TestTrendTagModel:
    """Testes para o modelo TrendTag."""
    
    def test_create_trend_tag(self, db_session):
        """Testa a criação de uma tag para tendência."""
        # Criar uma tendência
        trend = Trend(
            title="Vídeo de teste",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia"
        )
        
        db_session.add(trend)
        db_session.commit()
        
        # Criar uma tag
        tag = TrendTag(
            trend_id=trend.id,
            name="python"
        )
        
        db_session.add(tag)
        db_session.commit()
        
        # Verificar se a tag foi criada
        assert tag.id is not None
        assert tag.trend_id == trend.id
        assert tag.name == "python"
        
        # Verificar o relacionamento com a tendência
        assert tag.trend.id == trend.id
        assert tag.trend.title == "Vídeo de teste"
    
    def test_trend_tags_relationship(self, db_session):
        """Testa o relacionamento entre Trend e TrendTag."""
        # Criar uma tendência
        trend = Trend(
            title="Vídeo de teste",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia"
        )
        
        db_session.add(trend)
        db_session.commit()
        
        # Criar várias tags
        tags = [
            TrendTag(trend_id=trend.id, name="python"),
            TrendTag(trend_id=trend.id, name="programação"),
            TrendTag(trend_id=trend.id, name="tutorial")
        ]
        
        db_session.add_all(tags)
        db_session.commit()
        
        # Verificar se as tags estão associadas à tendência
        assert len(trend.tags) == 3
        assert any(tag.name == "python" for tag in trend.tags)
        assert any(tag.name == "programação" for tag in trend.tags)
        assert any(tag.name == "tutorial" for tag in trend.tags)

class TestAggregatedContentModel:
    """Testes para o modelo AggregatedContent."""
    
    def test_create_aggregated_content(self, db_session):
        """Testa a criação de conteúdo agregado."""
        # Criar uma tendência
        trend = Trend(
            title="Vídeo de teste",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia"
        )
        
        db_session.add(trend)
        db_session.commit()
        
        # Criar conteúdo agregado
        content = AggregatedContent(
            trend_id=trend.id,
            platform="youtube",
            title="Resumo do vídeo",
            content={"text": "Este é um resumo do vídeo de teste."},
            author="Canal de Teste",
            likes=500,
            comments=100,
            views=10000
        )
        
        db_session.add(content)
        db_session.commit()
        
        # Verificar se o conteúdo foi criado
        assert content.id is not None
        assert content.trend_id == trend.id
        assert content.platform == "youtube"
        assert content.title == "Resumo do vídeo"
        assert content.content["text"] == "Este é um resumo do vídeo de teste."
        assert content.author == "Canal de Teste"
        assert content.likes == 500
        assert content.comments == 100
        assert content.views == 10000
        
        # Verificar o relacionamento com a tendência
        assert content.trend.id == trend.id
        assert content.trend.title == "Vídeo de teste"
    
    def test_trend_content_relationship(self, db_session):
        """Testa o relacionamento entre Trend e AggregatedContent."""
        # Criar uma tendência
        trend = Trend(
            title="Vídeo de teste",
            url="https://youtube.com/video1",
            platform="youtube",
            category="tecnologia"
        )
        
        db_session.add(trend)
        db_session.commit()
        
        # Criar vários conteúdos agregados
        contents = [
            AggregatedContent(trend_id=trend.id, platform="youtube", title="Resumo", content={"type": "summary"}),
            AggregatedContent(trend_id=trend.id, platform="youtube", title="Transcrição", content={"type": "transcript"}),
            AggregatedContent(trend_id=trend.id, platform="youtube", title="Análise", content={"type": "analysis"})
        ]
        
        db_session.add_all(contents)
        db_session.commit()
        
        # Verificar se os conteúdos estão associados à tendência
        assert len(trend.aggregated_contents) == 3
        assert any(content.title == "Resumo" for content in trend.aggregated_contents)
        assert any(content.title == "Transcrição" for content in trend.aggregated_contents)
        assert any(content.title == "Análise" for content in trend.aggregated_contents) 