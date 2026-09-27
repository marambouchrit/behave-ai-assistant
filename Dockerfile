# Image de l'API FastAPI + pipeline RAG (CPU).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# torch en version CPU d'abord : sinon sentence-transformers tire la version
# CUDA (~2,5 Go inutiles sans GPU).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Modèles d'embedding et de reranking intégrés à l'image : démarrage immédiat,
# fonctionnement hors ligne, versions figées.
COPY config.py docker/download_models.py ./
RUN python download_models.py && rm download_models.py
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY . .

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

# Migrations puis serveur. Un seul worker : chaque worker charge les modèles
# (~2 Go de RAM) et la limite de connexion est en mémoire. --proxy-headers :
# l'IP réelle du client est lue dans X-Forwarded-For posé par nginx (l'API
# n'est jamais exposée directement). --root-path : l'API est servie sous /api.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*' --root-path /api"]
