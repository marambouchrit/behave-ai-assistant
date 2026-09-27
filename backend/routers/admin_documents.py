"""
routers/admin_documents.py
===========================
Routes d'administration : documents de la base de connaissances et
historique global des conversations.

La protection est posée au niveau du router : toute route ajoutée ici exige
require_admin_user (JWT valide ET role='admin' en base), sans possibilité de
l'oublier. La logique métier est dans services/document_service.py.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from backend.core.dependencies import require_admin_user
from backend.database.connection import get_db
from backend.database.crud import get_all_conversations, get_conversations_count
from backend.database.models import User
from backend.schemas import (
    ConversationRecord,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
    HistoryPageResponse,
)
from backend.services.document_service import (
    validate_file,
    save_file_to_disk,
    register_document_metadata,
    index_document,
    list_indexed_documents,
    delete_document_from_index,
    delete_file_from_disk,
)

logger = logging.getLogger(__name__)

# Seuls lettres, chiffres, "-", "_" et "." sont conservés : empêche les
# chemins du type "../../etc/passwd.pdf".
_SAFE_FILENAME_PATTERN = re.compile(r"[^\w\-.]")

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin_user)],
)


def _sanitize_filename(filename: str) -> str:
    name = filename.strip().replace(" ", "_")
    return _SAFE_FILENAME_PATTERN.sub("_", name)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Uploader et indexer un document",
    description=(
        "Upload un fichier PDF, DOCX ou TXT, le sauvegarde sur disque, déclare "
        "son module/titre dans le manifeste et l'indexe dans ChromaDB. "
        "Le document devient immédiatement disponible pour les questions utilisateurs."
    ),
)
async def upload_document(
    file:   UploadFile    = File(..., description="Fichier PDF, DOCX ou TXT à indexer"),
    module: Optional[str] = Form(None, max_length=100, description="Module BeHave du document"),
    title:  Optional[str] = Form(None, max_length=200, description="Titre lisible du document"),
    admin:  User          = Depends(require_admin_user),
) -> DocumentUploadResponse:
    """
    Route async car UploadFile.read() est une coroutine ; l'indexation
    (embedding, CPU-bound) est déléguée au threadpool pour ne pas bloquer la
    boucle d'événements.
    """
    logger.info("Admin '%s' uploade le fichier : %s", admin.username, file.filename)

    content = await file.read()
    error = validate_file(file.filename, len(content))
    if error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)

    safe_filename = _sanitize_filename(file.filename)

    try:
        file_path = save_file_to_disk(safe_filename, content)
        # Dans le manifeste, module et titre survivent à un run_indexation --reset.
        register_document_metadata(safe_filename, module=module, title=title)
        chunks_count = await run_in_threadpool(index_document, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception:
        logger.exception("Erreur d'indexation pour '%s'", safe_filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'indexation du document.",
        )

    return DocumentUploadResponse(
        filename=safe_filename,
        chunks_indexed=chunks_count,
        message=f"'{safe_filename}' indexé avec succès ({chunks_count} chunks).",
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lister les documents indexés",
    description=(
        "Retourne la liste de tous les documents distincts indexés dans ChromaDB, "
        "avec leur nombre de chunks et leur taille sur disque."
    ),
)
def get_documents() -> DocumentListResponse:
    documents = [DocumentInfo(**doc) for doc in list_indexed_documents()]
    return DocumentListResponse(documents=documents, total_documents=len(documents))


@router.delete(
    "/documents/{filename}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Supprimer un document",
    description=(
        "Supprime tous les chunks d'un document de ChromaDB "
        "et supprime le fichier du disque. "
        "Cette action est irréversible."
    ),
)
def delete_document(
    filename: str,
    admin: User = Depends(require_admin_user),
) -> DocumentDeleteResponse:
    """
    Supprime d'abord les chunks (opération principale), puis le fichier.
    Un fichier absent du disque n'est pas une erreur : les chunks, eux, sont
    bien retirés de l'index.
    """
    logger.info("Admin '%s' supprime le document : %s", admin.username, filename)

    safe_filename = _sanitize_filename(filename)
    chunks_deleted = delete_document_from_index(safe_filename)
    if chunks_deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{safe_filename}' introuvable dans l'index.",
        )

    if not delete_file_from_disk(safe_filename):
        logger.warning("Chunks supprimés mais fichier introuvable sur le disque : %s", safe_filename)

    return DocumentDeleteResponse(
        filename=safe_filename,
        chunks_deleted=chunks_deleted,
        message=f"'{safe_filename}' supprimé avec succès ({chunks_deleted} chunks retirés de l'index).",
    )


@router.get(
    "/history",
    response_model=HistoryPageResponse,
    status_code=status.HTTP_200_OK,
    summary="Historique global des conversations",
)
def get_history(
    skip:  int     = Query(0, ge=0),
    limit: int     = Query(50, ge=1, le=200),
    db:    Session = Depends(get_db),
) -> HistoryPageResponse:
    conversations = get_all_conversations(db, skip=skip, limit=limit)

    records = [
        ConversationRecord(
            id=c.id,
            username=c.user.username,
            question=c.question,
            answer=c.answer,
            module=c.module,
            sources=c.sources,
            created_at=c.created_at.isoformat(),
        )
        for c in conversations
    ]

    return HistoryPageResponse(
        conversations=records,
        total=get_conversations_count(db),
        skip=skip,
        limit=limit,
    )
