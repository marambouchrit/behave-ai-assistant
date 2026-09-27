"""
chain.py
========
Orchestrateur principal du pipeline RAG BeHave.

Flux par question :
    question + historique (fourni par l'appelant, lu en base)
        ↓ retriever.retrieve()             → recherche vectorielle + reranking
                                             → chunks filtrés et triés par pertinence
        ↓ build_prompt()                   → (system prompt, user_message + contexte chunks)
          ou build_no_context_prompt()       si aucun chunk pertinent
        ↓ _build_history_messages()        → historique borné (tours + budget tokens)
        ↓ Groq API (GPT OSS 20B)           → texte de la réponse
        ↓ RAGAnswer                        → module et sources lus dans la metadata
                                             des chunks — jamais dans le texte généré

Sans chunk pertinent (salutation, hors périmètre), la réponse n'a ni module ni
source, quel que soit le texte produit par le LLM.

Chaîne sans état :
    La chaîne ne conserve aucun historique. La table `conversations` (PostgreSQL)
    est la source de vérité ; l'appelant y lit les derniers échanges du chat et
    les passe à ask(). Une seule instance est partagée par tous les utilisateurs
    et tous les workers peuvent traiter n'importe quel chat.

Gestion d'erreurs :
    Les pannes attendues (base vectorielle, Groq indisponible, quota dépassé,
    réponse vide) lèvent une sous-classe de RAGError portant un message
    affichable. Toute autre exception est un bug et remonte telle quelle.
    Les retries sur Groq sont délégués au SDK (max_retries, backoff exponentiel).
"""

import logging
from dataclasses import dataclass

import groq
from chromadb.errors import ChromaError

from config import get_settings, require_settings
from ingestion.document_loader import Document
from rag.retriever import BeHaveRetriever
from rag.prompt_builder import build_no_context_prompt, build_prompt

logger = logging.getLogger(__name__)

# Heuristique d'estimation : ~4 caractères par token. Suffisant pour un budget
# (pas une limite dure) sans dépendre du tokenizer exact du modèle.
_CHARS_PER_TOKEN: int = 4


# ─── Types publics ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ConversationTurn:
    """Un échange passé question/réponse, tel que stocké en base."""
    question: str
    answer:   str


@dataclass(frozen=True)
class SourceRef:
    """Emplacement d'un extrait utilisé, tel qu'indexé (metadata ChromaDB)."""
    document: str
    title:    str | None = None
    page:     int | None = None
    section:  str | None = None

    @classmethod
    def from_chunk(cls, chunk: Document) -> "SourceRef":
        meta = chunk.metadata
        return cls(
            document=meta.get("source", ""),
            title=meta.get("title") or None,
            page=meta.get("page") or None,
            section=meta.get("section") or None,
        )


@dataclass(frozen=True)
class RAGAnswer:
    """Réponse du pipeline RAG."""
    content:     str
    module:      str | None
    sources:     list[SourceRef]
    chunks_used: int


class RAGError(Exception):
    """Panne attendue du pipeline. `user_message` est affichable tel quel."""
    user_message: str = (
        "Je suis temporairement indisponible. "
        "Veuillez réessayer dans quelques instants."
    )


class RetrievalUnavailableError(RAGError):
    """La base vectorielle n'a pas pu être interrogée."""
    user_message = (
        "La base documentaire est momentanément inaccessible. "
        "Veuillez réessayer dans quelques instants."
    )


class LLMUnavailableError(RAGError):
    """Groq injoignable, en erreur serveur, ou réponse vide."""


class LLMRateLimitedError(RAGError):
    """Quota Groq dépassé malgré les retries du SDK."""
    user_message = (
        "Trop de requêtes en cours. "
        "Veuillez patienter quelques secondes avant de réessayer."
    )


# ─── Fonctions privées ────────────────────────────────────────────────────────

def _relevance(chunk: Document) -> float:
    """Score de pertinence posé par le retriever (reranker, sinon cosinus)."""
    return chunk.metadata.get("relevance_score", 0.0)


def _best_chunk(chunks: list[Document]) -> Document | None:
    """Retourne le chunk le plus pertinent, None si la liste est vide."""
    if not chunks:
        return None
    return max(chunks, key=_relevance)


def _module_of(chunk: Document | None) -> str | None:
    """Module BeHave porté par la metadata ChromaDB du chunk, None si absent."""
    if chunk is None:
        return None
    return chunk.metadata.get("module") or None


def _sources_of(chunks: list[Document]) -> list[SourceRef]:
    """Sources distinctes des chunks, dans leur ordre de pertinence."""
    ranked = sorted(chunks, key=_relevance, reverse=True)
    return list(dict.fromkeys(SourceRef.from_chunk(c) for c in ranked))


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN + 1


def _build_history_messages(
    history: list[ConversationTurn],
    max_turns: int,
    token_budget: int,
) -> list[dict]:
    """
    Convertit l'historique en messages user/assistant pour le LLM.

    Garde les échanges les plus récents dans la double limite max_turns et
    token_budget. Un échange est inclus en entier ou pas du tout : la liste
    commence toujours par un message user.
    """
    recent = history[-max_turns:] if max_turns > 0 else []
    kept: list[ConversationTurn] = []
    budget = token_budget

    for turn in reversed(recent):
        cost = _estimate_tokens(turn.question) + _estimate_tokens(turn.answer)
        if cost > budget:
            break
        kept.append(turn)
        budget -= cost

    if len(kept) < len(history):
        logger.debug("Historique borné : %d → %d échanges.", len(history), len(kept))

    messages: list[dict] = []
    for turn in reversed(kept):
        messages.append({"role": "user",      "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    return messages


# ─── Classe principale ────────────────────────────────────────────────────────

class BeHaveRAGChain:
    """
    Chaîne RAG complète : retrieval → prompt → LLM → parsing.

    Sans état : une seule instance, créée au démarrage du serveur, est partagée
    par toutes les requêtes. L'historique est fourni à chaque appel de ask().

    Usage :
        chain  = BeHaveRAGChain(retriever=BeHaveRetriever())
        answer = chain.ask(question, history=[ConversationTurn(q, a), ...])
    """

    def __init__(self, retriever: BeHaveRetriever | None = None) -> None:
        require_settings("groq_api_key")
        self._settings = get_settings()

        self.client = groq.Groq(
            api_key=self._settings.groq_api_key,
            timeout=self._settings.groq_timeout_seconds,
            max_retries=self._settings.groq_max_retries,
        )
        self.retriever = retriever if retriever is not None else BeHaveRetriever()

        logger.info(
            "BeHaveRAGChain prête — modèle=%s | k=%d | reasoning_effort=%s",
            self._settings.groq_model_text,
            self._settings.rag_k,
            self._settings.groq_reasoning_effort,
        )

    @property
    def model_name(self) -> str:
        return self._settings.groq_model_text

    @property
    def max_history_turns(self) -> int:
        return self._settings.rag_max_history_turns

    def ask(
        self,
        question: str,
        history: list[ConversationTurn] | None = None,
    ) -> RAGAnswer:
        """
        Pose une question et retourne une réponse structurée.

        Args:
            question : question de l'utilisateur (non vide).
            history  : échanges précédents du chat, du plus ancien au plus récent.

        Raises:
            ValueError   : question vide.
            RAGError     : panne attendue (voir sous-classes), message affichable.
        """
        if not question or not question.strip():
            raise ValueError("ask() : la question ne peut pas être vide.")

        chunks = self._retrieve(question)
        if chunks:
            system_prompt, user_message = build_prompt(question, chunks)
        else:
            system_prompt, user_message = build_no_context_prompt(
                question, self.retriever.store.list_modules(),
            )

        messages = [
            {"role": "system", "content": system_prompt},
            *_build_history_messages(
                history or [],
                max_turns=self._settings.rag_max_history_turns,
                token_budget=self._settings.rag_history_token_budget,
            ),
            {"role": "user", "content": user_message},
        ]
        answer = RAGAnswer(
            content=self._complete(messages),
            module=_module_of(_best_chunk(chunks)),
            sources=_sources_of(chunks),
            chunks_used=len(chunks),
        )

        logger.info(
            "ask() OK — module=%s | chunks=%d | %d chars",
            answer.module, answer.chunks_used, len(answer.content),
        )
        return answer

    def _retrieve(self, question: str) -> list[Document]:
        try:
            return self.retriever.retrieve(question, k=self._settings.rag_k)
        except ChromaError as exc:
            logger.exception("Retrieval ChromaDB en échec : %s", exc)
            raise RetrievalUnavailableError() from exc

    def _complete(self, messages: list[dict]) -> str:
        """Appelle Groq et retourne le texte de la réponse (jamais vide)."""
        optional: dict = {}
        if self._settings.groq_reasoning_effort:
            optional["reasoning_effort"] = self._settings.groq_reasoning_effort

        try:
            response = self.client.chat.completions.create(
                model=self._settings.groq_model_text,
                max_tokens=self._settings.groq_max_tokens,
                temperature=self._settings.groq_temperature,
                messages=messages,
                **optional,
            )
        except groq.RateLimitError as exc:
            logger.warning("Groq : quota dépassé après retries (%s).", exc)
            raise LLMRateLimitedError() from exc
        except groq.APIConnectionError as exc:  # inclut APITimeoutError
            logger.error("Groq injoignable après retries : %s", exc)
            raise LLMUnavailableError() from exc
        except groq.InternalServerError as exc:
            logger.error("Groq en erreur serveur après retries : %s", exc)
            raise LLMUnavailableError() from exc

        choice  = response.choices[0]
        content = (choice.message.content or "").strip()
        if not content:
            logger.warning("Groq : réponse vide (finish_reason=%s).", choice.finish_reason)
            raise LLMUnavailableError()

        return content
