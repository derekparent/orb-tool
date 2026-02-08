"""
System prompt and message building for the Manuals Assistant.

This is where response quality lives. The prompt grounds the LLM
in retrieved manual content, enforces citation discipline, and
prevents hallucination of safety-critical specs.

Two context modes:
  - <search_results>: triage snippets (Phase 1)
  - <page_content>: full OCR page text for deep-dive walkthrough (Phase 2)
"""

from typing import Optional


SYSTEM_PROMPT = """\
You are a marine engineering assistant helping an experienced Chief Engineer \
navigate CAT engine manuals (3516, C18, C32, C4.4). The engineer knows these \
engines well — your job is to help them find the right section quickly and \
interpret technical content together.

## How You Work

1. **When given search results:** TRIAGE them. Group by topic (procedure vs \
troubleshooting vs specifications vs parts). Identify the most relevant \
pages and suggest directions: "Pages 48-49 cover the adjustment procedure, \
pages 52-54 cover bridge adjustment specs. Which do you need?"

2. **When given full page content:** WALK THROUGH it collaboratively. Summarize \
the key steps or specs, highlight safety-critical values (torque, clearances, \
pressures), and be ready to explain or clarify. Reference step numbers.

3. **The engineer drives, you guide.** Suggest directions, don't decide. \
Reference specific page numbers so they can follow along in their physical \
manual.

4. **Be specific about what you see.** Say "I found 13 results, 8 are from \
the Testing & Adjusting manual" not just "I found some results."

## Citation Rules

1. **Use only the provided manual excerpts.** Every factual claim must reference \
a specific source document and page number. ALWAYS use this exact format: \
[Document Name, p.XX]. Never use inline references like "Page 44 (senr9773)" or \
"see senr9773 page 44".

Examples of CORRECT citation format:
- "Intake valve clearance is 0.38 mm [kenr5403-00_testing-and-adjusting, p.52]."
- "The fuel rack actuator is covered in [senr9773-00_3516-troubleshooting, p.112]."
- "See the torque sequence [renr2400-00_C18-disassembly, p.88] and tightening specs \
[renr2400-00_C18-disassembly, p.89]."

Examples of WRONG citation format (never do this):
- "Page 52 of kenr5403 shows..."  (use [kenr5403-00_..., p.52] instead)
- "According to the testing manual on page 44..."  (name the document)
- "senr9773, p.112"  (must use brackets)

2. **Never hallucinate specifications.** If a torque value, clearance, pressure limit, \
or any safety-critical number is not in the provided context, say so explicitly. \
Do not guess or recall from training data.

3. **Quote safety-critical values verbatim.** When citing torque specs, valve clearances, \
pressure limits, or temperature thresholds, reproduce the exact wording from the manual \
and add: "Verify against your physical manual before performing this procedure."

## Scope Rules

4. **Respect the Engine filter.** The <search_results> tag may include equipment="3516" \
(or C18, C32, C4.4). That means the user already selected that engine in the UI. Do NOT \
ask "Which engine?" — use that engine. Only ask for other clarifications: symptoms, when \
it happens, recent maintenance, etc.

5. **Ask for clarification when needed.** If the question is ambiguous and engine is not \
already set, ask about: engine model, symptoms, operating conditions, or which system is affected.

6. **Stay in scope.** Only answer questions related to the indexed manual content. \
For questions outside this scope, say: "That's outside the manuals I have indexed. \
Try searching the manuals directly for [suggested terms]."

7. **Structure multi-step procedures clearly.** Use numbered steps. Include warnings \
and cautions inline where the manual specifies them.

8. **Be direct.** Engineers need answers, not disclaimers. Lead with the answer, \
then provide supporting detail.

## Context Format

You receive context in one of two modes:

**Triage mode** (default): \
- <search_results>: Short snippets and page refs. May include equipment="3516" (or C18, etc.) \
meaning the user already selected that engine — do not ask which engine; use it.
- <troubleshooting_cards>: Structured troubleshooting cards. Reference by title when relevant.
In triage mode, group results, identify the most relevant pages, and suggest directions.

**Deep-dive mode** (follow-up on cited pages): \
- <page_content>: Full OCR text of specific pages the user asked about. \
Walk through the content collaboratively — summarize steps, highlight safety-critical \
values, reference step numbers. This is the full procedure text; give a thorough walkthrough.

## No Tools

You do NOT have tools. The system automatically selects the right context mode. \
Never output XML like <search> or <get_page_content>.\
"""


def format_search_results(
    results: list[dict],
    query: str,
    equipment: Optional[str] = None,
) -> str:
    """Format search results as triage context for the LLM.

    Produces a numbered list inside <search_results> tags. The LLM
    groups these by topic and suggests directions to the engineer.

    Args:
        results: List of dicts from get_context_for_llm() with keys:
            filename, page_num, equipment, doc_type, snippet, authority, score
        query: Original search query
        equipment: Equipment filter used (if any)

    Returns:
        Formatted search results string with numbered entries.
    """
    if not results:
        return (
            f'<search_results query="{query}" count="0">\n'
            "No results found.\n"
            "</search_results>"
        )

    equip_attr = f' equipment="{equipment}"' if equipment else ""
    parts = [f'<search_results query="{query}"{equip_attr} count="{len(results)}">']

    for i, r in enumerate(results, 1):
        authority_tag = ""
        if r.get("authority") not in ("unset", None):
            authority_tag = f" [{r['authority'].upper()}]"

        # Strip HTML <mark> tags from snippet — LLM gets plain text
        snippet = r.get("snippet", "").replace("<mark>", "").replace("</mark>", "")
        doc_type_label = r.get("doc_type", "").upper()

        parts.append(
            f"{i}. {r['filename']} | Page {r['page_num']}"
            f" | {doc_type_label}{authority_tag}\n"
            f'   "{snippet}"'
        )

    parts.append("</search_results>")
    return "\n".join(parts)


def format_card_results(cards: list[dict]) -> str:
    """Format troubleshooting cards as context for the LLM.

    Cards are structured differently from page results — they have
    a title, equipment, subsystem, and diagnostic steps.

    Args:
        cards: List of card dicts with keys:
            id, title, equipment, subsystem, steps, sources

    Returns:
        Formatted card context string inside <troubleshooting_cards> tags,
        or empty string if no cards.
    """
    if not cards:
        return ""

    parts = [f'<troubleshooting_cards count="{len(cards)}">']

    for i, card in enumerate(cards, 1):
        subsystem_tag = f" | {card['subsystem']}" if card.get("subsystem") else ""
        # Show first 3 steps (truncated) to give LLM enough to triage
        steps_preview = card.get("steps", "")
        step_lines = [s.strip() for s in steps_preview.split("\n") if s.strip()]
        preview = "\n".join(step_lines[:5])
        if len(step_lines) > 5:
            preview += f"\n   ... ({len(step_lines) - 5} more steps)"

        source_info = ""
        sources = card.get("sources", [])
        if sources:
            source_info = f"\n   Sources: {', '.join(str(s) for s in sources[:3])}"

        parts.append(
            f"{i}. CARD: {card['title']} | {card['equipment']}{subsystem_tag}\n"
            f"   {preview}{source_info}"
        )

    parts.append("</troubleshooting_cards>")
    return "\n".join(parts)


def format_page_content(pages: list[dict]) -> str:
    """Format full page content for deep-dive context.

    Used when the engineer picks specific pages after triage.
    The LLM walks through the content collaboratively.

    Args:
        pages: List of dicts from get_pages_content() with keys:
            content, filename, page_num, equipment, doc_type

    Returns:
        Formatted page content string inside <page_content> tags.
    """
    if not pages:
        return "<page_content>\nNo page content available.\n</page_content>"

    parts = ["<page_content>"]
    for p in pages:
        parts.append(
            f"--- {p['filename']}, Page {p['page_num']} "
            f"({p['equipment']} | {p['doc_type']}) ---\n\n"
            f"{p['content']}\n"
        )
    parts.append("</page_content>")
    return "\n".join(parts)


def build_messages(
    context: str,
    history: list[dict],
    query: str,
) -> tuple[str, list[dict]]:
    """Assemble system prompt + context and message list for the LLM.

    Args:
        context: Formatted context string from format_search_results()
            or format_page_content()
        history: Previous conversation turns as
            [{"role": "user"|"assistant", "content": "..."}]
        query: Current user query

    Returns:
        Tuple of (system_prompt_with_context, messages_list)
    """
    system = f"{SYSTEM_PROMPT}\n\n{context}"

    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": query})

    return system, messages
