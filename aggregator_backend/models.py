import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define a URL do banco de dados. Por padrão, utiliza um arquivo SQLite em ./data/aggregator.db.
# Você pode definir a variável de ambiente DATABASE_URL para apontar para outro banco, como PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/aggregator.db")

# Cria o engine. Para SQLite, o parâmetro check_same_thread deve ser False em ambientes multi-thread.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Cria a fábrica de sessões.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos declarativos.
Base = declarative_base()

class AggregatedContent(Base):
    __tablename__ = "aggregated_content"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False)
    keyword = Column(String(100), nullable=False)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
