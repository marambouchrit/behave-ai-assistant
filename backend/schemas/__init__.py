"""
schemas
=======
Modèles Pydantic des requêtes et réponses de l'API.
"""

from pydantic import BaseModel, Field


class ChatCreateRequest(BaseModel):
    """Corps de POST /chats"""
    title: str = Field(default="Nouvelle conversation", max_length=200)


class ChatRenameRequest(BaseModel):
    """Corps de PATCH /chats/{chat_id}"""
    title: str = Field(..., min_length=1, max_length=200)


class ChatItem(BaseModel):
    """Un chat dans la liste GET /chats"""
    id:         int
    title:      str
    created_at: str


class ChatListResponse(BaseModel):
    """Réponse de GET /chats"""
    chats: list[ChatItem]
    total: int


class ChatRequest(BaseModel):
    """Corps de POST /chat"""
    question: str = Field(..., min_length=1, max_length=2000)
    chat_id:  int


class SourceItem(BaseModel):
    """Extrait de documentation utilisé pour une réponse (metadata ChromaDB)."""
    document: str
    title:    str | None = None
    page:     int | None = None
    section:  str | None = None


class ChatResponse(BaseModel):
    answer:      str
    module:      str | None = None
    sources:     list[SourceItem] = Field(default_factory=list)
    chat_id:     int
    chunks_used: int


class ChatTurnItem(BaseModel):
    """Un échange question/réponse d'un chat (GET /chats/{chat_id}/messages)"""
    id:         int
    question:   str
    answer:     str
    module:     str | None = None
    sources:    list[SourceItem] = Field(default_factory=list)
    created_at: str


class ChatTurnListResponse(BaseModel):
    """Réponse de GET /chats/{chat_id}/messages"""
    chat_id: int
    turns:   list[ChatTurnItem]
    total:   int


class ModuleListResponse(BaseModel):
    """Réponse de GET /modules — modules présents dans l'index."""
    modules: list[str]


class HealthResponse(BaseModel):
    status:             str
    chromadb_documents: int
    model:              str


class DocumentInfo(BaseModel):
    filename:     str   = Field(..., description="Nom du fichier")
    chunks_count: int   = Field(..., description="Nombre de chunks indexés")
    uploaded_at:  str   = Field(..., description="Date d'indexation ISO 8601")
    file_size_kb: float = Field(..., description="Taille en Ko")


class DocumentListResponse(BaseModel):
    documents:       list[DocumentInfo]
    total_documents: int


class DocumentUploadResponse(BaseModel):
    filename:       str
    chunks_indexed: int
    message:        str
    success:        bool = True


class DocumentDeleteResponse(BaseModel):
    filename:       str
    chunks_deleted: int
    message:        str
    success:        bool = True


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class TokenResponse(BaseModel):
    access_token:       str
    token_type:         str = "bearer"
    expires_in_minutes: int
    username:           str
    role:               str


class UserResponse(BaseModel):
    id:       int
    username: str
    role:     str


class ConversationRecord(BaseModel):
    """Un échange dans l'historique global (GET /admin/history)"""
    id:         int
    username:   str
    question:   str
    answer:     str
    module:     str | None
    sources:    list[SourceItem]
    created_at: str


class HistoryPageResponse(BaseModel):
    conversations: list[ConversationRecord]
    total:         int
    skip:          int
    limit:         int
