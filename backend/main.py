"""
main.py
=======
Backend FastAPI — BeHave AI Chatbot

Lancement (depuis la racine du projet) :
    alembic upgrade head              # schéma de la base à jour
    uvicorn backend.main:app --reload

Les comptes (dont le premier administrateur) se créent avec
`python -m backend.manage` : voir backend/manage.py.
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import get_settings, require_settings
from rag.chain import BeHaveRAGChain, ConversationTurn, LLMRateLimitedError, RAGError
from rag.retriever import BeHaveRetriever
from backend.core.dependencies import require_user_token
from backend.core.rate_limit import install_rate_limiting
from backend.database.connection import get_db
from backend.database.models import Chat, User
from backend.database.crud import (
    save_conversation,
    create_chat,
    get_user_chats,
    get_chat_by_id,
    rename_chat,
    delete_chat,
    get_chat_conversations,
    get_recent_chat_conversations,
    count_chat_conversations,
    hide_chat_conversations,
)
from backend.routers.auth import router as auth_router
from backend.routers.admin_documents import router as admin_documents_router
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    ChatCreateRequest,
    ChatRenameRequest,
    ChatItem,
    ChatListResponse,
    ChatTurnItem,
    ChatTurnListResponse,
    HealthResponse,
    ModuleListResponse,
)
from backend.services.document_service import set_vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Démarrage : vérifie la configuration et charge le pipeline RAG (une seule
    chaîne, sans état, partagée par toutes les requêtes). Le schéma de la base
    est géré par Alembic, les comptes par backend/manage.py.
    """
    require_settings("jwt_secret_key", "database_url", "groq_api_key")

    logger.info("Initialisation du pipeline RAG...")
    retriever = BeHaveRetriever()
    set_vector_store(retriever.store)
    app.state.rag_chain = BeHaveRAGChain(retriever=retriever)
    logger.info("Pipeline RAG prêt.")

    yield


app = FastAPI(
    title="BeHave AI Assistant",
    description="Assistant conversationnel RAG pour la suite BeHave — Siryos",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

install_rate_limiting(app)

app.include_router(auth_router)
app.include_router(admin_documents_router)


def get_rag_chain(request: Request) -> BeHaveRAGChain:
    """Dépendance FastAPI : chaîne RAG partagée, créée au démarrage."""
    return request.app.state.rag_chain


def _get_owned_chat_or_404(chat_id: int, user: User, db: Session) -> Chat:
    """Retourne le chat s'il appartient à l'utilisateur, sinon lève une 404."""
    chat_obj = get_chat_by_id(db, chat_id=chat_id, user_id=user.id)
    if chat_obj is None:
        raise HTTPException(status_code=404, detail="Chat introuvable.")
    return chat_obj


@app.post("/chats", response_model=ChatItem)
def create_new_chat(
    body:         ChatCreateRequest,
    current_user: User    = Depends(require_user_token),
    db:           Session = Depends(get_db),
):
    """Crée un nouveau chat pour l'utilisateur connecté."""
    chat = create_chat(db, user_id=current_user.id, title=body.title)
    return ChatItem(
        id=chat.id,
        title=chat.title,
        created_at=chat.created_at.isoformat(),
    )


@app.get("/chats", response_model=ChatListResponse)
def list_chats(
    current_user: User    = Depends(require_user_token),
    db:           Session = Depends(get_db),
):
    """Retourne tous les chats de l'utilisateur connecté."""
    chats = get_user_chats(db, user_id=current_user.id)
    return ChatListResponse(
        chats=[
            ChatItem(id=c.id, title=c.title, created_at=c.created_at.isoformat())
            for c in chats
        ],
        total=len(chats),
    )


@app.patch("/chats/{chat_id}", response_model=ChatItem)
def rename_existing_chat(
    chat_id:      int,
    body:         ChatRenameRequest,
    current_user: User    = Depends(require_user_token),
    db:           Session = Depends(get_db),
):
    """Renomme un chat existant."""
    chat = rename_chat(db, chat_id=chat_id, user_id=current_user.id, new_title=body.title)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat introuvable.")
    return ChatItem(id=chat.id, title=chat.title, created_at=chat.created_at.isoformat())


@app.delete("/chats/{chat_id}")
def delete_existing_chat(
    chat_id:      int,
    current_user: User    = Depends(require_user_token),
    db:           Session = Depends(get_db),
):
    """Supprime un chat et ses conversations."""
    ok = delete_chat(db, chat_id=chat_id, user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat introuvable.")
    return {"message": "Chat supprimé.", "chat_id": chat_id}


@app.get("/chats/{chat_id}/messages", response_model=ChatTurnListResponse)
def list_chat_messages(
    chat_id:      int,
    current_user: User    = Depends(require_user_token),
    db:           Session = Depends(get_db),
):
    """Retourne les échanges visibles d'un chat, du plus ancien au plus récent."""
    _get_owned_chat_or_404(chat_id, current_user, db)
    conversations = get_chat_conversations(db, chat_id=chat_id)
    return ChatTurnListResponse(
        chat_id=chat_id,
        turns=[
            ChatTurnItem(
                id=c.id,
                question=c.question,
                answer=c.answer,
                module=c.module,
                sources=c.sources,
                created_at=c.created_at.isoformat(),
            )
            for c in conversations
        ],
        total=len(conversations),
    )


@app.delete("/chats/{chat_id}/messages")
def reset_chat_messages(
    chat_id:      int,
    current_user: User    = Depends(require_user_token),
    db:           Session = Depends(get_db),
):
    """
    Soft reset d'un chat : les échanges sont masqués du chat et du contexte LLM,
    mais conservés en base pour l'historique admin.
    """
    _get_owned_chat_or_404(chat_id, current_user, db)
    hidden = hide_chat_conversations(db, chat_id=chat_id)
    return {"message": "Chat réinitialisé.", "chat_id": chat_id, "hidden": hidden}


@app.get("/health", response_model=HealthResponse)
def health_check(rag_chain: BeHaveRAGChain = Depends(get_rag_chain)):
    info = rag_chain.retriever.store.get_collection_info()
    return HealthResponse(
        status="ok",
        chromadb_documents=info["document_count"],
        model=f"{rag_chain.model_name} (Groq)",
    )


@app.get("/modules", response_model=ModuleListResponse)
def list_modules(
    current_user: User           = Depends(require_user_token),
    rag_chain:    BeHaveRAGChain = Depends(get_rag_chain),
):
    """Modules BeHave présents dans l'index (metadata ChromaDB)."""
    return ModuleListResponse(modules=rag_chain.retriever.store.list_modules())


_AUTO_TITLE_MAX_LEN: int = 40


@app.post("/chat", response_model=ChatResponse)
def chat(
    body:         ChatRequest,
    current_user: User           = Depends(require_user_token),
    db:           Session        = Depends(get_db),
    rag_chain:    BeHaveRAGChain = Depends(get_rag_chain),
):
    """
    Reçoit une question et la traite par le pipeline RAG.

    Le contexte conversationnel est relu en base (derniers échanges visibles
    du chat) à chaque requête : la table `conversations` est la source de vérité.
    Seules les réponses effectivement produites par le LLM sont enregistrées :
    une panne (Groq, base vectorielle) renvoie 429/503 sans rien persister.

    Route synchrone (def) : FastAPI l'exécute dans un threadpool, ce qui évite
    de bloquer la boucle d'événements pendant l'embedding et l'appel Groq.

    Auto-renommage : à la première question d'un chat, le titre est automatiquement
    mis à jour avec les premiers mots de la question.
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La question ne peut pas être vide.")

    chat_id = _get_owned_chat_or_404(body.chat_id, current_user, db).id

    history = [
        ConversationTurn(question=c.question, answer=c.answer)
        for c in get_recent_chat_conversations(
            db, chat_id=chat_id, limit=rag_chain.max_history_turns,
        )
    ]

    try:
        answer = rag_chain.ask(question, history=history)
    except LLMRateLimitedError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.user_message)
    except RAGError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.user_message)

    sources = [asdict(source) for source in answer.sources]

    save_conversation(
        db=db,
        user_id=current_user.id,
        question=question,
        answer=answer.content,
        module=answer.module,
        sources=sources,
        chat_id=chat_id,
    )

    if count_chat_conversations(db, chat_id=chat_id) == 1:
        auto_title = (
            question[:_AUTO_TITLE_MAX_LEN] + "..."
            if len(question) > _AUTO_TITLE_MAX_LEN
            else question
        )
        rename_chat(
            db,
            chat_id=chat_id,
            user_id=current_user.id,
            new_title=auto_title,
        )

    return ChatResponse(
        answer=answer.content,
        module=answer.module,
        sources=sources,
        chat_id=chat_id,
        chunks_used=answer.chunks_used,
    )
