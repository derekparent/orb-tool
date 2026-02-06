"""
Chat Service — Context assembly and conversation management.

Orchestrates the RAG pipeline: query → search → context → LLM → response.
Manages conversation history and token budgets.
"""

import logging
from collections.abc import Iterator
from typing import Optional

from services.llm_service import LLMService, LLMServiceError, get_llm_service
from services.manuals_service import get_context_for_llm, search_manuals
from prompts.manuals_assistant import format_context, build_messages

logger = logging.getLogger(__name__)

# Token budget: Sonnet 4.5 has 200k context, but we stay lean
MAX_CONTEXT_TOKENS = 4000  # RAG excerpts budget
MAX_HISTORY_TOKENS = 3000  # Conversation history budget
MAX_TURNS = 10             # Max conversation turns kept


class ChatServiceError(Exception):
    """Raised when the chat service encounters an error."""


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
        equipment: Optional equipment filter for RAG search
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

    # Trim history to max turns
    trimmed_history = _trim_history(history, max_turns, llm)

    # Retrieve RAG context
    context_results = get_context_for_llm(query, equipment=equipment, limit=5)
    context_str = format_context(context_results)

    # Trim context if over budget
    context_str = _trim_to_token_budget(context_str, max_context_tokens, llm)

    # Build messages
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

    trimmed_history = _trim_history(history, max_turns, llm)

    context_results = get_context_for_llm(query, equipment=equipment, limit=5)
    context_str = format_context(context_results)
    context_str = _trim_to_token_budget(context_str, max_context_tokens, llm)

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
    results = search_manuals(query, equipment=equipment, limit=10, boost_primary=True)
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
