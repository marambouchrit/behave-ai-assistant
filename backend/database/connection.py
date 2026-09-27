"""
database/connection.py
=======================
Connexion PostgreSQL via SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import get_settings, require_settings

require_settings("database_url")

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

def get_db():
    """
    Générateur de session SQLAlchemy.
    Utilisé via Depends(get_db) dans les routes FastAPI.
    Garantit la fermeture de la session après chaque requête.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
