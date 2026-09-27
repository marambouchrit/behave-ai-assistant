"""
core/security.py
================
Hachage des mots de passe (bcrypt) et émission / vérification des JWT.

Le token ne porte que l'identité (claim "sub" = username) et son expiration.
Le rôle n'y figure pas : il est relu en base à chaque requête par les
dépendances de core/dependencies.py, si bien qu'un changement de rôle
s'applique immédiatement.
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status

from config import get_settings, require_settings

ALGORITHM = "HS256"

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _secret_key() -> str:
    require_settings("jwt_secret_key")
    return get_settings().jwt_secret_key


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Émet un JWT signé pour `subject` (username), valable JWT_EXPIRE_MINUTES par défaut."""
    lifetime = expires_delta or timedelta(minutes=get_settings().jwt_expire_minutes)
    payload  = {"sub": subject, "exp": datetime.now(timezone.utc) + lifetime}
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """
    Retourne le username porté par le token.

    Raises:
        HTTPException 401 : signature invalide, token expiré ou mal formé.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré. Veuillez vous reconnecter.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception

    subject = payload.get("sub")
    if subject is None:
        raise credentials_exception
    return subject
