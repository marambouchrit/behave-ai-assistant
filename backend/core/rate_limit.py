"""
core/rate_limit.py
==================
Limitation du nombre de requêtes par adresse IP (slowapi).

Utilisée sur /auth/login contre le brute-force (LOGIN_RATE_LIMIT, défaut
5/minute). Les compteurs sont en mémoire, propres à chaque processus : avec
plusieurs workers, la limite effective est multipliée par leur nombre (un
stockage partagé, ex. Redis via `storage_uri`, lèverait cette limite).

Derrière un reverse proxy, l'IP vue est celle du proxy : lancer uvicorn avec
--proxy-headers pour prendre en compte X-Forwarded-For.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def _rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # Même format d'erreur que le reste de l'API ({"detail": ...}).
    window_seconds = exc.limit.limit.get_expiry()
    return JSONResponse(
        status_code=429,
        content={"detail": f"Trop de tentatives. Réessayez dans {window_seconds} secondes."},
        headers={"Retry-After": str(window_seconds)},
    )


def install_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded)
