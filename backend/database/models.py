"""
database/models.py
==================
Modèles SQLAlchemy — tables PostgreSQL.

Tables :
  - users         : comptes utilisateurs avec rôle
  - chats         : conversations (sessions nommées) par utilisateur
  - conversations : échanges question/réponse dans un chat — source de vérité
                    de l'historique (contexte LLM et affichage)

Le schéma est versionné par Alembic (backend/migrations/) : toute modification
d'un modèle doit s'accompagner d'une migration.
"""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    JSON, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.orm import relationship
from backend.database.connection import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    user  = "user"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    role          = Column(Enum(UserRole), nullable=False, default=UserRole.user)
    created_at    = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    chats         = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"


class Chat(Base):
    __tablename__ = "chats"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title      = Column(String(200), nullable=False, default="Nouvelle conversation")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user          = relationship("User", back_populates="chats")
    conversations = relationship(
        "Conversation",
        back_populates="chat",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Chat id={self.id} user_id={self.user_id} title={self.title!r}>"


class Conversation(Base):
    __tablename__ = "conversations"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chat_id    = Column(Integer, ForeignKey("chats.id"), nullable=True, index=True)
    question   = Column(Text, nullable=False)
    answer     = Column(Text, nullable=False)
    module     = Column(String(100), nullable=True)
    # [{"document", "title", "page", "section"}, ...] — metadata des chunks utilisés
    sources    = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # Soft reset : masqué du chat et du contexte LLM, conservé pour l'admin.
    hidden_at  = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="conversations")
    chat = relationship("Chat", back_populates="conversations")

    __table_args__ = (
        Index("ix_conversations_chat_id_created_at", "chat_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id} chat_id={self.chat_id}>"