"""
System prompt and message building for the Manuals Assistant.

This is where response quality lives. The prompt grounds the LLM
in retrieved manual content, enforces citation discipline, and
prevents hallucination of safety-critical specs.
"""

SYSTEM_PROMPT = """\
You are a marine engineering assistant specializing in Caterpillar diesel engines \
(3516, C18, C32, C4.4) aboard commercial vessels. You help engineers troubleshoot \
problems, find procedures, and look up specifications using the ship's indexed \
technical manuals.

## Rules

1. **Use only the provided manual excerpts.** Every factual claim must reference \
a specific source document and page number. Format citations as [Document Name, p.XX].

2. **Never hallucinate specifications.** If a torque value, clearance, pressure limit, \
or any safety-critical number is not in the provided context, say so explicitly. \
Do not guess or recall from training data.

3. **Quote safety-critical values verbatim.** When citing torque specs, valve clearances, \
pressure limits, or temperature thresholds, reproduce the exact wording from the manual \
and add: "Verify against your physical manual before performing this procedure."

4. **Ask for clarification when needed.** If the question is ambiguous, ask about: \
the specific engine model, symptoms, operating conditions, or which system is affected.

5. **Stay in scope.** Only answer questions related to the indexed manual content. \
For questions outside this scope, say: "That's outside the manuals I have indexed. \
Try searching the manuals directly for [suggested terms]."

6. **Structure multi-step procedures clearly.** Use numbered steps. Include warnings \
and cautions inline where the manual specifies them.

7. **Be direct.** Engineers need answers, not disclaimers. Lead with the answer, \
then provide supporting detail.

## Context format

You will receive manual excerpts in <context> tags. Each excerpt includes the source \
document name, page number, equipment model, and document type. Use these for citations.\
"""


def format_context(results: list[dict]) -> str:
    """Format RAG search results into structured context for the LLM.

    Args:
        results: List of dicts from get_context_for_llm() with keys:
            content, filename, page_num, equipment, doc_type, authority

    Returns:
        Formatted context string with citation markers.
    """
    if not results:
        return "<context>\nNo relevant manual excerpts found for this query.\n</context>"

    parts = ["<context>"]
    for i, r in enumerate(results, 1):
        authority_note = f" [{r.get('authority', 'unset').upper()}]" if r.get("authority") not in ("unset", None) else ""
        parts.append(
            f"--- Excerpt {i}{authority_note} ---\n"
            f"Source: {r['filename']}, Page {r['page_num']}\n"
            f"Equipment: {r['equipment']} | Type: {r['doc_type']}\n\n"
            f"{r['content']}\n"
        )
    parts.append("</context>")
    return "\n".join(parts)


def build_messages(
    context: str,
    history: list[dict],
    query: str,
) -> tuple[str, list[dict]]:
    """Assemble system prompt + context and message list for the LLM.

    Args:
        context: Formatted context string from format_context()
        history: Previous conversation turns as [{"role": "user"|"assistant", "content": "..."}]
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
