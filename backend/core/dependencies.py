"""
core/dependencies.py
====================
Dépendances FastAPI pour l'authentification unifiée.

require_user_token  → tout utilisateur connecté (user ET admin)
require_admin_user  → uniquement role='admin'
"""

import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.security import decode_token
from backend.database.connection import get_db
from backend.database.crud import get_user_by_username
from backend.database.models import User, UserRole

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def require_user_token(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Protège les routes accessibles à tout utilisateur connecté.
    Décode le JWT, vérifie que l'user existe en base.
    Retourne l'objet User complet pour accès à id, role, etc.
    """
    username = decode_token(token)

    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_admin_user(
    current_user: User = Depends(require_user_token),
) -> User:
    """
    Protège les routes réservées aux admins.
    Étend require_user_token en vérifiant role='admin'.
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé. Droits administrateur requis.",
        )
    return current_user