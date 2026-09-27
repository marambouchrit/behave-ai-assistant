"""
database/crud.py
================
Opérations CRUD sur PostgreSQL.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from backend.core.security import hash_password, verify_password
from backend.database.models import User, Conversation, Chat, UserRole

logger = logging.getLogger(__name__)

# Hash bcrypt valide vérifié quand l'utilisateur n'existe pas : le temps de
# réponse ne révèle pas si un username existe.
_DUMMY_PASSWORD_HASH = hash_password("timing-attack-prevention")


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def create_user(
    db: Session,
    username: str,
    password: str,
    role: UserRole = UserRole.user,
) -> User:
    """
    Crée un nouvel utilisateur dans la base.
    Raises ValueError si le username existe déjà.
    """
    if get_user_by_username(db, username):
        raise ValueError(f"Username '{username}' déjà utilisé.")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Utilisateur créé : %s (role=%s)", username, role)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """
    Vérifie les credentials. Retourne User si valide, None sinon.
    Un hash est toujours vérifié, que l'utilisateur existe ou non.
    """
    user = get_user_by_username(db, username)
    hash_to_check = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_ok   = verify_password(password, hash_to_check)

    if not user or not password_ok:
        return None
    return user


def set_user_password(db: Session, user: User, password: str) -> None:
    """Remplace le mot de passe d'un utilisateur."""
    user.password_hash = hash_password(password)
    db.commit()
    logger.info("Mot de passe réinitialisé : %s", user.username)


def set_user_role(db: Session, user: User, role: UserRole) -> None:
    """Change le rôle d'un utilisateur."""
    user.role = role
    db.commit()
    logger.info("Rôle modifié : %s → %s", user.username, role.value)


def create_chat(
    db: Session,
    user_id: int,
    title: str = "Nouvelle conversation",
) -> Chat:
    """Crée un nouveau chat pour un utilisateur."""
    chat = Chat(user_id=user_id, title=title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    logger.info("Chat créé : id=%d user_id=%d title=%r", chat.id, user_id, title)
    return chat


def get_user_chats(db: Session, user_id: int) -> list[Chat]:
    """Retourne tous les chats d'un utilisateur, plus récents en premier."""
    return (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .all()
    )


def get_chat_by_id(db: Session, chat_id: int, user_id: int) -> Chat | None:
    """Retourne un chat par son id, uniquement si il appartient à l'utilisateur."""
    return (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == user_id)
        .first()
    )


def rename_chat(
    db: Session,
    chat_id: int,
    user_id: int,
    new_title: str,
) -> Chat | None:
    """Renomme un chat. Retourne None si le chat n'existe pas ou n'appartient pas à l'user."""
    chat = get_chat_by_id(db, chat_id, user_id)
    if not chat:
        return None
    chat.title = new_title
    db.commit()
    db.refresh(chat)
    return chat


def delete_chat(db: Session, chat_id: int, user_id: int) -> bool:
    """
    Supprime un chat et toutes ses conversations (cascade).
    Retourne True si supprimé, False si introuvable.
    """
    chat = get_chat_by_id(db, chat_id, user_id)
    if not chat:
        return False
    db.delete(chat)
    db.commit()
    logger.info("Chat supprimé : id=%d user_id=%d", chat_id, user_id)
    return True


def save_conversation(
    db: Session,
    user_id: int,
    question: str,
    answer: str,
    module: str | None = None,
    sources: list[dict] | None = None,
    chat_id: int | None = None,
) -> Conversation:
    """Sauvegarde un échange question/réponse en base."""
    conversation = Conversation(
        user_id=user_id,
        chat_id=chat_id,
        question=question,
        answer=answer,
        module=module,
        sources=sources or [],
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _visible_chat_conversations(db: Session, chat_id: int):
    """Requête de base : échanges non masqués d'un chat."""
    return db.query(Conversation).filter(
        Conversation.chat_id == chat_id,
        Conversation.hidden_at.is_(None),
    )


def get_chat_conversations(db: Session, chat_id: int) -> list[Conversation]:
    """Retourne tous les échanges visibles d'un chat, du plus ancien au plus récent."""
    return (
        _visible_chat_conversations(db, chat_id)
        .order_by(Conversation.created_at.asc(), Conversation.id.asc())
        .all()
    )


def get_recent_chat_conversations(
    db: Session,
    chat_id: int,
    limit: int,
) -> list[Conversation]:
    """
    Retourne les `limit` derniers échanges visibles d'un chat, remis dans
    l'ordre chronologique (plus ancien en premier) pour le contexte LLM.
    """
    recent = (
        _visible_chat_conversations(db, chat_id)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(recent))


def count_chat_conversations(db: Session, chat_id: int) -> int:
    """Nombre total d'échanges d'un chat, masqués inclus."""
    return db.query(Conversation).filter(Conversation.chat_id == chat_id).count()


def hide_chat_conversations(db: Session, chat_id: int) -> int:
    """
    Soft reset : masque tous les échanges visibles d'un chat.
    Retourne le nombre d'échanges masqués.
    """
    hidden = _visible_chat_conversations(db, chat_id).update(
        {Conversation.hidden_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )
    db.commit()
    logger.info("Chat %d réinitialisé : %d échange(s) masqué(s)", chat_id, hidden)
    return hidden


def get_all_conversations(
    db: Session,
    skip: int = 0,
    limit: int = 50,
) -> list[Conversation]:
    """Retourne toutes les conversations paginées, plus récentes en premier."""
    return (
        db.query(Conversation)
        .order_by(Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_conversations_count(db: Session) -> int:
    """Retourne le nombre total de conversations."""
    return db.query(Conversation).count()