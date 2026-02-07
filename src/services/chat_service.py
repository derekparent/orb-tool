"""
Chat Service — Context assembly and conversation management.

Orchestrates the RAG pipeline: query → search → context → LLM → response.
Manages conversation history and token budgets.

Two-phase context:
  Phase 1 (triage): search_manuals() snippets → LLM groups & suggests directions
  Phase 2 (follow-up): re-search with refined query → LLM narrows focus
"""

import logging
import re
from collections.abc import Iterator
from typing import Optional

from services.llm_service import LLMService, LLMServiceError, get_llm_service
from services.manuals_service import get_context_for_llm, search_manuals
from prompts.manuals_assistant import format_search_results, build_messages

logger = logging.getLogger(__name__)

# Token budget: Sonnet has 200k context, but we stay lean
MAX_CONTEXT_TOKENS = 4000  # RAG excerpts budget
MAX_HISTORY_TOKENS = 3000  # Conversation history budget
MAX_TURNS = 10             # Max conversation turns kept

# Equipment detection: case-insensitive match for known engine models
_EQUIPMENT_PATTERN = re.compile(r"\b(3516|C18|C32|C4\.4)\b", re.IGNORECASE)

# Canonical equipment names (normalize case from regex matches)
_EQUIPMENT_CANONICAL = {
    "3516": "3516",
    "c18": "C18",
    "c32": "C32",
    "c4.4": "C4.4",
}


# Stop words to strip from conversational queries before FTS5 search.
# FTS5 uses implicit AND, so "What is the valve lash procedure" requires
# ALL words including "What", "is", "the" — returning 0 results.
# Stripping these converts conversational input to keyword queries.
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "where", "when", "why", "how",
    "do", "does", "did", "have", "has", "had", "having",
    "can", "could", "would", "should", "shall", "will", "may", "might",
    "i", "me", "my", "we", "our", "you", "your", "it", "its",
    "this", "that", "these", "those",
    "of", "in", "on", "at", "to", "for", "with", "from", "by", "about",
    "and", "or", "but", "not", "if", "then", "so",
    "tell", "show", "find", "get", "give", "explain", "describe",
    "need", "want", "look", "help",
})

# Maximum content words before switching from implicit AND to explicit OR.
# FTS5 implicit AND requires ALL terms on one page. With >3 content words
# that's too restrictive for OCR'd manual text. OR gives broad recall and
# BM25 naturally ranks pages with more matching terms higher.
_MAX_AND_TERMS = 3


class ChatServiceError(Exception):
    """Raised when the chat service encounters an error."""


def _extract_search_query(query: str) -> str:
    """Convert a conversational query into FTS5-friendly search terms.

    Pipeline:
      1. Strip punctuation and stop words
      2. If ≤3 content words remain → implicit AND (precise)
      3. If >3 content words remain → explicit OR (broad recall)

    BM25 ranking naturally scores pages with more matching terms higher,
    so OR still produces well-ordered results. The LLM triages after.

    Note: When OR syntax is present, prepare_search_query() in
    manuals_service.py skips its own expansion (acronyms, synonyms).
    That's acceptable — broad OR recall is sufficient for chat.

    Examples:
        "valve lash"
        → "valve lash"  (≤3 terms, implicit AND)

        "What is the valve lash adjustment procedure for the 3516?"
        → "valve OR lash OR adjustment OR procedure OR 3516"  (>3 terms, OR)

        "How do I check jacket water pressure on C18?"
        → "check OR jacket OR water OR pressure OR C18"  (>3 terms, OR)

        "3516 fuel rack"
        → "3516 fuel rack"  (≤3 terms, implicit AND)

    Args:
        query: Natural language question from the user

    Returns:
        FTS5 query string (implicit AND for short, explicit OR for long)
    """
    # Remove question marks and trailing punctuation
    cleaned = query.strip().rstrip("?!.")

    # Tokenize preserving model numbers like C4.4, C18, 3516
    tokens = re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", cleaned)

    # Filter stop words (case-insensitive) but keep technical terms
    keywords = [t for t in tokens if t.lower() not in _STOP_WORDS]

    if not keywords:
        # Fallback: if everything was stripped, use original
        return query

    if len(keywords) <= _MAX_AND_TERMS:
        # Short query: implicit AND is fine (precise matching)
        return " ".join(keywords)

    # Long query: use OR for broad recall, let BM25 rank by relevance
    return " OR ".join(keywords)


def detect_equipment(query: str) -> Optional[str]:
    """Auto-detect equipment model from query text.

    Scans for known CAT engine identifiers. Returns the first match
    normalized to canonical form, or None if no equipment found.

    Known values: 3516, C18, C32, C4.4

    Args:
        query: User's question text

    Returns:
        Canonical equipment string or None
    """
    match = _EQUIPMENT_PATTERN.search(query)
    if match:
        return _EQUIPMENT_CANONICAL.get(match.group(1).lower(), match.group(1))
    return None


def _resolve_equipment(
    explicit: Optional[str],
    query: str,
) -> Optional[str]:
    """Resolve equipment filter: explicit dropdown wins, then auto-detect.

    Args:
        explicit: Equipment value from UI dropdown (None or empty = not set)
        query: User's query text for auto-detection fallback

    Returns:
        Equipment filter string or None
    """
    if explicit:
        return explicit
    return detect_equipment(query)


def get_chat_response(
    query: str,
    history: list[dict],
    equipment: Optional[str] = None,
    max_context_tokens: int = MAX_CONTEXT_TOKENS,
    max_turns: int = MAX_TURNS,
) -> str:
    """Get a complete (non-streaming) chat response.

    Args:
        query: User's question
        history: Previous conversation turns
        equipment: Optional equipment filter from UI dropdown
        max_context_tokens: Token budget for RAG context
        max_turns: Max history turns to include

    Returns:
        Full response text

    Raises:
        ChatServiceError if LLM service unavailable or fails
    """
    llm = get_llm_service()
    if not llm:
        raise ChatServiceError("Chat assistant is not configured (missing API key)")

    # Resolve equipment: dropdown wins, then auto-detect from query
    resolved_equipment = _resolve_equipment(equipment, query)

    # Trim history to max turns
    trimmed_history = _trim_history(history, max_turns, llm)

    # Extract keywords for FTS5 search (strip stop words from conversational input)
    search_query = _extract_search_query(query)

    # Retrieve RAG context via search_manuals() (single search path)
    context_results = get_context_for_llm(
        search_query, equipment=resolved_equipment, limit=10
    )
    context_str = format_search_results(
        context_results, query, equipment=resolved_equipment
    )

    # Trim context if over budget
    context_str = _trim_to_token_budget(context_str, max_context_tokens, llm)

    # Build messages — original query goes to LLM, not the keyword extraction
    system, messages = build_messages(context_str, trimmed_history, query)

    try:
        return llm.complete(system, messages)
    except LLMServiceError as e:
        logger.error(f"LLM error: {e}")
        raise ChatServiceError(str(e))


def stream_chat_response(
    query: str,
    history: list[dict],
    equipment: Optional[str] = None,
    max_context_tokens: int = MAX_CONTEXT_TOKENS,
    max_turns: int = MAX_TURNS,
) -> Iterator[str]:
    """Stream a chat response token by token.

    Same pipeline as get_chat_response() but yields text deltas.

    Yields:
        Text delta strings

    Raises:
        ChatServiceError if LLM service unavailable or fails
    """
    llm = get_llm_service()
    if not llm:
        raise ChatServiceError("Chat assistant is not configured (missing API key)")

    # Resolve equipment: dropdown wins, then auto-detect from query
    resolved_equipment = _resolve_equipment(equipment, query)

    trimmed_history = _trim_history(history, max_turns, llm)

    # Extract keywords for FTS5 search (strip stop words from conversational input)
    search_query = _extract_search_query(query)

    # Retrieve RAG context via search_manuals() (single search path)
    context_results = get_context_for_llm(
        search_query, equipment=resolved_equipment, limit=10
    )
    context_str = format_search_results(
        context_results, query, equipment=resolved_equipment
    )
    context_str = _trim_to_token_budget(context_str, max_context_tokens, llm)

    # Build messages — original query goes to LLM, not the keyword extraction
    system, messages = build_messages(context_str, trimmed_history, query)

    try:
        yield from llm.stream(system, messages)
    except LLMServiceError as e:
        logger.error(f"LLM streaming error: {e}")
        raise ChatServiceError(str(e))


def get_fallback_results(query: str, equipment: Optional[str] = None) -> list[dict]:
    """Get FTS5 search results as fallback when LLM is unavailable.

    Returns results formatted for display in the chat UI.
    """
    search_query = _extract_search_query(query)
    results = search_manuals(search_query, equipment=equipment, limit=10, boost_primary=True)
    return [
        {
            "filename": r["filename"],
            "page_num": r["page_num"],
            "equipment": r["equipment"],
            "doc_type": r["doc_type"],
            "snippet": r["snippet"],
        }
        for r in results
    ]


def _trim_history(
    history: list[dict],
    max_turns: int,
    llm: LLMService,
) -> list[dict]:
    """Trim conversation history to fit within turn and token limits.

    Keeps the most recent turns. Each turn is a user+assistant pair.
    """
    if not history:
        return []

    # Keep last N messages (each turn = 2 messages: user + assistant)
    max_messages = max_turns * 2
    trimmed = history[-max_messages:]

    # Further trim if over token budget
    total_tokens = sum(llm.count_tokens(m["content"]) for m in trimmed)
    while trimmed and total_tokens > MAX_HISTORY_TOKENS:
        removed = trimmed.pop(0)
        total_tokens -= llm.count_tokens(removed["content"])

    return trimmed


def _trim_to_token_budget(text: str, max_tokens: int, llm: LLMService) -> str:
    """Trim text to approximate token budget."""
    estimated = llm.count_tokens(text)
    if estimated <= max_tokens:
        return text

    # Rough trim: 4 chars per token
    max_chars = max_tokens * 4
    return text[:max_chars] + "\n\n[Context truncated to fit token budget]"
