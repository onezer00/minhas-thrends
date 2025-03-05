import os
import datetime
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, ForeignKey, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Obtém a URL do banco de dados da variável de ambiente
DATABASE_URL = os.getenv("DATABASE_URL")

# Verifica se a URL do banco de dados foi fornecida
if not DATABASE_URL:
    # Fallback para SQLite em um diretório temporário (funciona no Render)
    import tempfile
    temp_dir = tempfile.gettempdir()
    db_path = os.path.join(temp_dir, "trendpulse.db")
    DATABASE_URL = f"sqlite:///{db_path}"
    logger.warning(f"DATABASE_URL não configurada! Usando SQLite temporário: {DATABASE_URL}")
    logger.warning(f"Diretório temporário: {temp_dir} (deve ter permissões de escrita)")
else:
    logger.info(f"Usando banco de dados configurado: {DATABASE_URL}")
    
    # Para MySQL/PostgreSQL no Render, pode ser necessário ajustar a URL
    if "mysql" in DATABASE_URL:
        # Verifica se precisamos adicionar o driver pymysql
        if "pymysql" not in DATABASE_URL and "mysql://" in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")
            logger.info(f"URL ajustada para usar pymysql: {DATABASE_URL}")
        
        # Substitui localhost pelo nome do serviço no Render se necessário
        if "@localhost" in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace("@localhost", "@mysql")
            logger.info(f"URL ajustada para ambiente Render (localhost -> mysql): {DATABASE_URL}")

# Tenta criar o engine com tratamento de erro
try:
    # Para SQLite, o parâmetro check_same_thread deve ser False em ambientes multi-thread
    if DATABASE_URL.startswith("sqlite"):
        logger.info(f"Criando engine SQLite com check_same_thread=False")
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        logger.info(f"Criando engine para {DATABASE_URL.split('://')[0]}")
        engine = create_engine(DATABASE_URL)
    
    # Testa a conexão
    with engine.connect() as conn:
        logger.info(f"Conexão com o banco de dados estabelecida com sucesso!")
        
        # Tenta obter a versão do banco
        try:
            version = conn.execute("SELECT VERSION()").scalar()
            logger.info(f"Versão do banco de dados: {version}")
        except Exception as e:
            logger.warning(f"Não foi possível obter a versão do banco: {str(e)}")
            
except Exception as e:
    logger.error(f"Erro ao conectar ao banco de dados: {str(e)}")
    logger.error(f"URL do banco: {DATABASE_URL}")
    
    # Em caso de falha, tenta um fallback mais simples para SQLite em memória
    logger.warning("Tentando fallback para SQLite em memória...")
    DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(DATABASE_URL)
    logger.info("Usando SQLite em memória como último recurso")

# Cria a fábrica de sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos declarativos
Base = declarative_base()

class Trend(Base):
    """
    Modelo para armazenar tendências de diferentes plataformas.
    """
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)  # Usando Text para garantir suporte a títulos longos
    description = Column(Text, nullable=True)
    platform = Column(String(50), nullable=False, index=True)  # twitter, youtube, reddit
    category = Column(String(50), nullable=True, index=True)   # tecnologia, entretenimento, etc.
    external_id = Column(String(255), nullable=True, index=True)  # Aumentado para 255
    author = Column(String(255), nullable=True)  # Aumentado para 255
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    published_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    thumbnail = Column(Text, nullable=True)  # Alterado para Text para URLs longas
    content = Column(JSON, nullable=True)  # Conteúdo completo em JSON
    volume = Column(Integer, default=0)  # Volume de menções, visualizações, etc.
    url = Column(Text, nullable=True)  # URL da tendência
    
    # Relacionamento com tags
    tags = relationship("TrendTag", back_populates="trend", cascade="all, delete-orphan")
    
    # Relacionamento com conteúdo agregado
    aggregated_contents = relationship("AggregatedContent", back_populates="trend", cascade="all, delete-orphan")

    def to_dict(self):
        """
        Converte o modelo para um dicionário compatível com o formato esperado pelo frontend.
        """
        time_ago = self._calculate_time_ago()
        
        # Obtém as tags relacionadas
        tag_list = [tag.name for tag in self.tags]
        
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "platform": self.platform,
            "category": self.category,
            "author": self.author,
            "views": f"{self.views:,}".replace(",", ".") if self.views > 1000 else str(self.views),
            "likes": self.likes,
            "comments": self.comments,
            "timeAgo": time_ago,
            "tags": tag_list,
            "thumbnail": self.thumbnail,
            "url": self.url
        }
    
    def _calculate_time_ago(self):
        """
        Calcula o tempo decorrido desde a publicação em formato amigável.
        """
        now = datetime.datetime.utcnow()
        diff = now - self.published_at
        
        # Menos de 1 hora
        if diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} {'minutos' if minutes > 1 else 'minuto'}"
        
        # Menos de 1 dia
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} {'horas' if hours > 1 else 'hora'}"
        
        # Menos de 30 dias
        elif diff.days < 30:
            return f"{diff.days} {'dias' if diff.days > 1 else 'dia'}"
        
        # Menos de 12 meses
        elif diff.days < 365:
            months = int(diff.days / 30)
            return f"{months} {'meses' if months > 1 else 'mês'}"
        
        # Mais de 1 ano
        else:
            years = int(diff.days / 365)
            return f"{years} {'anos' if years > 1 else 'ano'}"


class TrendTag(Base):
    """
    Modelo para armazenar tags associadas às tendências.
    """
    __tablename__ = "trend_tags"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False, index=True)  # Aumentado para 255
    
    # Relacionamento com a tendência
    trend = relationship("Trend", back_populates="tags")


class AggregatedContent(Base):
    """
    Modelo para armazenar conteúdo agregado relacionado às tendências (tweets, posts, vídeos).
    """
    __tablename__ = "aggregated_contents"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(50), nullable=False)
    title = Column(Text, nullable=True)  # Alterado para Text
    content = Column(JSON, nullable=True)
    author = Column(String(255), nullable=True)  # Aumentado para 255
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relacionamento com a tendência
    trend = relationship("Trend", back_populates="aggregated_contents")


# Função para criar todas as tabelas no banco de dados
def create_tables():
    Base.metadata.create_all(bind=engine)


# Função para obter uma sessão do banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()