"""
Chat Service — Context assembly and conversation management.

Orchestrates the RAG pipeline: query → search → context → LLM → response.
Manages conversation history and token budgets.

Context is snippets-only: we send search_manuals() snippets (short excerpts),
not full page text. get_pages_content() and format_page_content() exist for
a future "deep-dive" phase but are not wired into the chat pipeline — so the
assistant cannot "load" full procedure pages. It can only triage and cite
page numbers; for full steps the user must open the PDF to those pages.
"""

import logging
import re
from collections.abc import Iterator
from typing import Optional

from services.llm_service import LLMService, LLMServiceError, get_llm_service
from services.manuals_service import get_context_for_llm, search_manuals, search_cards
from prompts.manuals_assistant import format_search_results, format_card_results, build_messages

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

# Synonym expansions for common engineer terms — improves recall when manuals
# use different wording (e.g. "clearance" vs "lash", "protrusion" vs "height")
_QUERY_SYNONYMS = {
    "lash": "clearance",
    "clearance": "lash",
    "height": "protrusion",
    "protrusion": "height",
    "jwac": "jacket water aftercooler",
    "scac": "seawater charge air cooler",
    "turbo": "turbocharger",
    "turbocharger": "turbo",
    "aftercooler": "intercooler",
}

# Known compound phrases in marine engineering manuals.
# When adjacent tokens form a known phrase, we quote them for FTS5 phrase matching.
# This prevents "oil filter replacement" from matching any page with just "oil".
_KNOWN_PHRASES = frozenset({
    "oil filter", "fuel filter", "oil cooler", "oil pressure",
    "fuel pressure", "fuel rack", "fuel system", "fuel pump",
    "fuel delivery", "fuel supply", "fuel injector",
    "valve lash", "valve clearance", "valve adjustment", "valve bridge",
    "valve cover", "valve guide", "valve seat", "valve spring",
    "jacket water", "charge air", "water pump", "water temperature",
    "turbo charger", "air filter", "air intake",
    "cylinder head", "cylinder block", "cylinder liner",
    "crankshaft seal", "main bearing", "connecting rod",
    "lube oil", "oil pan",
    "starting motor", "starting system",
    "exhaust manifold", "exhaust temperature",
    "engine control", "control module",
    "top dead center",
})

# Phrase-level synonyms: when a detected phrase has known alternatives,
# add them as OR expansions so both wordings match.
_PHRASE_SYNONYMS = {
    "valve lash": ["valve clearance", "valve adjustment"],
    "valve clearance": ["valve lash"],
    "valve adjustment": ["valve lash", "valve clearance"],
    "oil pressure": ["lube oil pressure"],
    "fuel system": ["fuel delivery", "fuel supply"],
    "fuel filter": ["fuel filtration"],
    "jacket water": ["jacket water aftercooler"],
    "top dead center": ["tdc"],
    "fuel delivery": ["fuel system", "fuel supply"],
}

# Minimum results needed from AND pass before falling back to OR.
_MIN_AND_RESULTS = 3


class ChatServiceError(Exception):
    """Raised when the chat service encounters an error."""


def _tokenize_query(query: str) -> list[str]:
    """Strip punctuation and stop words, returning content keywords.

    Preserves model numbers like C4.4, C18, 3516.
    """
    cleaned = query.strip().rstrip("?!.")
    tokens = re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", cleaned)
    keywords = [t for t in tokens if t.lower() not in _STOP_WORDS]
    return keywords if keywords else []


def _detect_phrases(keywords: list[str]) -> list[str]:
    """Detect known compound phrases and quote them for FTS5.

    Scans adjacent keyword pairs (bigrams) against _KNOWN_PHRASES.
    Matched pairs are quoted as FTS5 phrases; unmatched tokens pass through.

    Example:
        ["oil", "filter", "replacement"] → ['"oil filter"', "replacement"]
        ["3516", "valve", "lash"] → ["3516", '"valve lash"']
    """
    if len(keywords) < 2:
        return list(keywords)

    result: list[str] = []
    i = 0
    while i < len(keywords):
        if i + 1 < len(keywords):
            bigram = f"{keywords[i].lower()} {keywords[i + 1].lower()}"
            if bigram in _KNOWN_PHRASES:
                result.append(f'"{keywords[i]} {keywords[i + 1]}"')
                i += 2
                continue
        result.append(keywords[i])
        i += 1
    return result


def _expand_with_synonyms(phrased: list[str], keywords: list[str]) -> str:
    """Build AND query with OR synonym alternatives.

    Handles both phrase-level synonyms (valve lash → valve clearance)
    and word-level synonyms (turbo → turbocharger).

    Returns FTS5 query string, e.g.:
        '"valve lash" OR "valve clearance"'
        '3516 "fuel rack"'
        'turbo OR turbocharger'
    """
    base = " ".join(phrased)
    alternatives: list[str] = []

    # Phrase-level synonyms: check each quoted phrase
    for term in phrased:
        if term.startswith('"'):
            bare = term.strip('"').lower()
            if bare in _PHRASE_SYNONYMS:
                for alt in _PHRASE_SYNONYMS[bare]:
                    # Build full alternative by swapping this phrase
                    alt_phrased = [f'"{alt}"' if t == term else t for t in phrased]
                    alternatives.append(" ".join(alt_phrased))

    # Word-level synonyms: check each unquoted token
    for i, term in enumerate(phrased):
        if term.startswith('"'):
            continue
        syn = _QUERY_SYNONYMS.get(term.lower())
        if syn and syn.lower() not in base.lower():
            alt_phrased = list(phrased)
            alt_phrased[i] = syn
            alternatives.append(" ".join(alt_phrased))

    if alternatives:
        # Deduplicate, keep base first
        seen = {base}
        unique_alts = []
        for alt in alternatives:
            if alt not in seen:
                seen.add(alt)
                unique_alts.append(alt)
        if unique_alts:
            return " OR ".join([base] + unique_alts)

    return base


def _extract_search_query(query: str) -> str:
    """Convert a conversational query into a precise FTS5 AND query.

    Pipeline:
      1. Strip punctuation and stop words
      2. Detect known compound phrases and quote them
      3. Add synonym alternatives as OR branches
      4. Return AND query (all terms required within each OR branch)

    This is the first-pass (precise) query. If it returns too few
    results, the caller falls back to _extract_broad_query().

    Examples:
        "valve lash"
        → '"valve lash" OR "valve clearance" OR "valve adjustment"'

        "What is the oil filter replacement procedure?"
        → '"oil filter" replacement procedure'  (AND with phrase)

        "3516 fuel rack"
        → '3516 "fuel rack"'  (AND with phrase)

    Args:
        query: Natural language question from the user

    Returns:
        FTS5 query string using implicit AND with quoted phrases
    """
    keywords = _tokenize_query(query)
    if not keywords:
        return query

    # Detect and quote known compound phrases
    phrased = _detect_phrases(keywords)

    # Expand with synonym alternatives
    return _expand_with_synonyms(phrased, keywords)


def _extract_broad_query(query: str) -> str:
    """Convert a conversational query into a broad FTS5 OR query.

    Used as fallback when the precise AND query returns too few results.
    OR gives broad recall; BM25 ranks pages with more terms higher.

    Examples:
        "What is the oil filter replacement procedure?"
        → '"oil filter" OR oil OR filter OR replacement OR procedure'
    """
    keywords = _tokenize_query(query)
    if not keywords:
        return query

    # Detect phrases for the OR list too
    phrased = _detect_phrases(keywords)

    # Build OR terms: include both quoted phrases and individual words
    or_terms: list[str] = list(phrased)
    for kw in keywords:
        if kw not in or_terms:
            or_terms.append(kw)

    # Add synonyms
    for kw in keywords:
        syn = _QUERY_SYNONYMS.get(kw.lower())
        if syn and syn not in or_terms:
            or_terms.append(syn)

    return " OR ".join(or_terms)


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


def _search_with_fallback(
    query: str,
    equipment: Optional[str],
    limit: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Two-pass search: precise AND first, broad OR fallback.

    Pass 1: AND query with phrase detection (e.g. '"oil filter" replacement')
    Pass 2: OR fallback if AND returned fewer than _MIN_AND_RESULTS

    Also searches troubleshooting cards for relevant structured guidance.

    Returns:
        Tuple of (page_results, card_results)
    """
    and_query = _extract_search_query(query)
    results = get_context_for_llm(and_query, equipment=equipment, limit=limit)

    if len(results) < _MIN_AND_RESULTS:
        or_query = _extract_broad_query(query)
        if or_query != and_query:
            results = get_context_for_llm(or_query, equipment=equipment, limit=limit)

    # Search troubleshooting cards (use broad query for better recall)
    card_query = _extract_broad_query(query) if len(_tokenize_query(query)) > 3 else _extract_search_query(query)
    try:
        cards = search_cards(card_query, equipment=equipment, limit=5)
    except Exception:
        cards = []

    return results, cards


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

    # Two-pass search: AND first, OR fallback; also searches cards
    context_results, card_results = _search_with_fallback(query, resolved_equipment, limit=10)
    context_str = format_search_results(
        context_results, query, equipment=resolved_equipment
    )
    cards_str = format_card_results(card_results)
    if cards_str:
        context_str = f"{context_str}\n\n{cards_str}"

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

    # Two-pass search: AND first, OR fallback; also searches cards
    context_results, card_results = _search_with_fallback(query, resolved_equipment, limit=10)
    context_str = format_search_results(
        context_results, query, equipment=resolved_equipment
    )
    cards_str = format_card_results(card_results)
    if cards_str:
        context_str = f"{context_str}\n\n{cards_str}"
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

    Uses the same two-pass search strategy (AND first, OR fallback).
    Returns results formatted for display in the chat UI.
    """
    and_query = _extract_search_query(query)
    results = search_manuals(and_query, equipment=equipment, limit=10, boost_primary=True)

    if len(results) < _MIN_AND_RESULTS:
        or_query = _extract_broad_query(query)
        if or_query != and_query:
            results = search_manuals(or_query, equipment=equipment, limit=10, boost_primary=True)

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
