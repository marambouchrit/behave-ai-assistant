"""
prompt_builder.py
=================
Construction des prompts envoyés au LLM.

Deux cas :
    build_prompt()            : des chunks pertinents ont été trouvés → le LLM
                                répond à partir de ce contexte uniquement.
    build_no_context_prompt() : aucun chunk pertinent (salutation, question
                                hors périmètre) → le LLM salue ou décline.

Le LLM ne produit que du texte. Il n'a jamais à indiquer un module ni une
source : ces informations viennent exclusivement de la metadata des chunks
récupérés (chain.py). Les modules cités au LLM sont ceux réellement présents
dans l'index — aucune liste n'est écrite en dur.
"""

import logging

from ingestion.document_loader import Document

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT: str = """Tu es BeHave Assistant, un assistant IA spécialisé \
dans la suite logicielle BeHave de Siryos.
Tu réponds aux questions en te basant UNIQUEMENT sur les extraits de la \
documentation officielle BeHave fournis avec la question.

RÈGLES :
- Réponds TOUJOURS dans la même langue que la question de l'utilisateur
- Base-toi uniquement sur les extraits fournis, sans rien inventer
- Sois précis et concis ; structure la réponse (étapes, listes) quand c'est utile
- Si les extraits ne contiennent pas l'information demandée, dis-le clairement
- Ne cite pas les numéros d'extraits ni les noms de fichiers : les sources \
sont affichées automatiquement à l'utilisateur
"""

_NO_CONTEXT_SYSTEM_PROMPT: str = """Tu es BeHave Assistant, un assistant IA \
spécialisé dans la suite logicielle BeHave de Siryos. {scope}

Aucun extrait de la documentation BeHave ne correspond au message de \
l'utilisateur.

RÈGLES :
- Réponds TOUJOURS dans la même langue que le message de l'utilisateur
- S'il s'agit d'une salutation, d'un remerciement ou d'une question sur ton \
rôle, réponds poliment et brièvement, et invite l'utilisateur à poser une \
question sur BeHave
- Sinon, explique en une ou deux phrases que tu ne peux répondre qu'aux \
questions sur la suite BeHave et que tu n'as pas trouvé d'information à ce \
sujet dans la documentation
- N'invente JAMAIS d'information sur BeHave ni sur un autre sujet
"""


def _scope_sentence(modules: list[str]) -> str:
    if not modules:
        return "Tu réponds aux questions sur la suite BeHave."
    return f"Tu couvres les modules suivants : {', '.join(modules)}."


def _source_label(chunk: Document) -> str:
    """Étiquette lisible d'un extrait : module — titre (p. X / section)."""
    meta     = chunk.metadata
    document = meta.get("title") or meta.get("source", "documentation")
    location = (
        f"p. {meta['page']}" if meta.get("page")
        else meta.get("section")
    )
    parts = [meta.get("module"), f"{document} ({location})" if location else document]
    return " — ".join(p for p in parts if p)


def _build_context(chunks: list[Document]) -> str:
    """Formate les chunks récupérés en un bloc de contexte pour le prompt."""
    return "\n\n".join(
        f"[Extrait {i + 1} — {_source_label(c)}] :\n{c.page_content}"
        for i, c in enumerate(chunks)
    )


def build_prompt(question: str, chunks: list[Document]) -> tuple[str, str]:
    """
    Construit le prompt pour une question accompagnée d'extraits pertinents.

    Returns:
        Tuple (system_prompt, user_message).
    """
    user_message = (
        f"Extraits de la documentation BeHave :\n\n{_build_context(chunks)}\n\n"
        f"---\n"
        f"Question : {question}"
    )
    return _SYSTEM_PROMPT, user_message


def build_no_context_prompt(question: str, modules: list[str]) -> tuple[str, str]:
    """
    Construit le prompt quand aucun extrait n'est pertinent.

    Args:
        modules : modules présents dans l'index (metadata ChromaDB).

    Returns:
        Tuple (system_prompt, user_message).
    """
    system_prompt = _NO_CONTEXT_SYSTEM_PROMPT.format(scope=_scope_sentence(modules))
    return system_prompt, question
