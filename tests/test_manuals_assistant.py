"""Tests for manuals_assistant.py — prompt construction, citation rules, context formatting.

Covers:
  - SYSTEM_PROMPT content validation (citation rules, collaborative framing)
  - format_search_results (empty, single, multiple, authority tags, equipment attr)
  - format_card_results (empty, single, multiple, step truncation, sources)
  - format_page_content (empty, single, multiple pages)
  - build_messages (system+context assembly, history handling)
  - Citation format rules enforcement (bracket format required)
  - Context truncation behavior
  - Equipment-specific prompt variations
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ─────────────────────────────────────────────────────────────────
# Unit Tests: SYSTEM_PROMPT content
# ─────────────────────────────────────────────────────────────────

class TestSystemPrompt:
    """Validate system prompt contains all required sections."""

    def test_has_citation_rules(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "Citation Rules" in SYSTEM_PROMPT

    def test_requires_bracket_format(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Must instruct LLM to use [Doc, p.XX] format
        assert "[" in SYSTEM_PROMPT
        assert "p." in SYSTEM_PROMPT

    def test_forbids_paren_citations(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Prompt should explicitly call out wrong formats
        assert "WRONG" in SYSTEM_PROMPT
        assert "parentheses" in SYSTEM_PROMPT.lower() or "()" in SYSTEM_PROMPT

    def test_has_hallucination_prevention(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "hallucinate" in SYSTEM_PROMPT.lower()

    def test_has_safety_critical_warning(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "safety-critical" in SYSTEM_PROMPT.lower()
        assert "verify" in SYSTEM_PROMPT.lower()

    def test_has_collaborative_framing(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "engineer drives" in SYSTEM_PROMPT.lower()

    def test_has_triage_mode(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "triage" in SYSTEM_PROMPT.lower()
        assert "<search_results>" in SYSTEM_PROMPT

    def test_has_deep_dive_mode(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "<page_content>" in SYSTEM_PROMPT

    def test_has_scope_rules(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "scope" in SYSTEM_PROMPT.lower()

    def test_has_engine_filter_instruction(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Should tell LLM to respect equipment filter
        assert "engine filter" in SYSTEM_PROMPT.lower() or "equipment" in SYSTEM_PROMPT.lower()

    def test_no_tools_disclaimer(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        assert "no tool" in SYSTEM_PROMPT.lower() or "do NOT have tools" in SYSTEM_PROMPT

    def test_correct_citation_examples(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Must contain CORRECT examples with bracket format
        assert "[kenr5403-00_testing-and-adjusting, p.52]" in SYSTEM_PROMPT

    def test_wrong_citation_examples(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Must contain WRONG examples to teach format
        assert "Page 52 of kenr5403" in SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────────
# Unit Tests: format_search_results
# ─────────────────────────────────────────────────────────────────

class TestFormatSearchResultsDetailed:
    """Detailed tests for search result formatting."""

    def test_empty_results(self):
        from prompts.manuals_assistant import format_search_results

        ctx = format_search_results([], "test query")
        assert 'count="0"' in ctx
        assert "No results found" in ctx
        assert "<search_results" in ctx
        assert "</search_results>" in ctx

    def test_query_in_output(self):
        from prompts.manuals_assistant import format_search_results

        ctx = format_search_results([], "valve lash procedure")
        assert 'query="valve lash procedure"' in ctx

    def test_equipment_attr_present(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "content",
                "authority": "unset",
                "score": 1.0,
            }
        ]
        ctx = format_search_results(results, "test", equipment="3516")
        assert 'equipment="3516"' in ctx

    def test_equipment_attr_absent_when_none(self):
        from prompts.manuals_assistant import format_search_results

        ctx = format_search_results([], "test", equipment=None)
        assert "equipment=" not in ctx

    def test_primary_authority_tag(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "content",
                "authority": "primary",
                "score": 1.0,
            }
        ]
        ctx = format_search_results(results, "test")
        assert "[PRIMARY]" in ctx

    def test_secondary_authority_tag(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "content",
                "authority": "secondary",
                "score": 1.0,
            }
        ]
        ctx = format_search_results(results, "test")
        assert "[SECONDARY]" in ctx

    def test_unset_authority_no_tag(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "O&M",
                "snippet": "content",
                "authority": "unset",
                "score": 2.0,
            }
        ]
        ctx = format_search_results(results, "test")
        assert "[UNSET]" not in ctx
        assert "[PRIMARY]" not in ctx
        assert "[SECONDARY]" not in ctx

    def test_mark_tags_stripped(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "The <mark>valve</mark> <mark>lash</mark> procedure",
                "authority": "unset",
                "score": 1.0,
            }
        ]
        ctx = format_search_results(results, "valve lash")
        assert "<mark>" not in ctx
        assert "valve" in ctx
        assert "lash" in ctx

    def test_doc_type_uppercased(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "content",
                "authority": "unset",
                "score": 1.0,
            }
        ]
        ctx = format_search_results(results, "test")
        assert "TESTING" in ctx

    def test_numbering(self):
        from prompts.manuals_assistant import format_search_results

        results = [
            {
                "filename": f"doc{i}.pdf",
                "page_num": i,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": f"content {i}",
                "authority": "unset",
                "score": float(i),
            }
            for i in range(1, 4)
        ]
        ctx = format_search_results(results, "test")
        assert "1. doc1.pdf" in ctx
        assert "2. doc2.pdf" in ctx
        assert "3. doc3.pdf" in ctx
        assert 'count="3"' in ctx


# ─────────────────────────────────────────────────────────────────
# Unit Tests: format_card_results (detailed)
# ─────────────────────────────────────────────────────────────────

class TestFormatCardResultsDetailed:
    """Detailed tests for troubleshooting card formatting."""

    def test_empty_returns_empty_string(self):
        from prompts.manuals_assistant import format_card_results

        assert format_card_results([]) == ""

    def test_subsystem_included(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {
                "id": "1",
                "title": "Low Oil Pressure",
                "equipment": "3516",
                "subsystem": "lubrication",
                "steps": "Check oil level",
                "sources": [],
            }
        ]
        ctx = format_card_results(cards)
        assert "lubrication" in ctx

    def test_no_subsystem_omitted(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {
                "id": "1",
                "title": "General Alert",
                "equipment": "3516",
                "subsystem": None,
                "steps": "Check all",
                "sources": [],
            }
        ]
        ctx = format_card_results(cards)
        # Should not have a trailing " | " with nothing
        assert "| None" not in ctx

    def test_steps_truncated_to_5(self):
        from prompts.manuals_assistant import format_card_results

        long_steps = "\n".join([f"Step {i}: Do thing {i}" for i in range(1, 10)])
        cards = [
            {
                "id": "1",
                "title": "Multi-step Card",
                "equipment": "3516",
                "subsystem": "fuel",
                "steps": long_steps,
                "sources": [],
            }
        ]
        ctx = format_card_results(cards)
        assert "Step 1" in ctx
        assert "Step 5" in ctx
        assert "4 more steps" in ctx

    def test_sources_included(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {
                "id": "1",
                "title": "Card",
                "equipment": "3516",
                "subsystem": None,
                "steps": "Step 1",
                "sources": [{"filename": "doc.pdf", "page": 44}],
            }
        ]
        ctx = format_card_results(cards)
        assert "Sources:" in ctx

    def test_no_sources_no_line(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {
                "id": "1",
                "title": "Card",
                "equipment": "3516",
                "subsystem": None,
                "steps": "Step 1",
                "sources": [],
            }
        ]
        ctx = format_card_results(cards)
        assert "Sources:" not in ctx

    def test_xml_tags(self):
        from prompts.manuals_assistant import format_card_results

        cards = [
            {
                "id": "1",
                "title": "Card",
                "equipment": "3516",
                "subsystem": None,
                "steps": "Step 1",
                "sources": [],
            }
        ]
        ctx = format_card_results(cards)
        assert "<troubleshooting_cards" in ctx
        assert "</troubleshooting_cards>" in ctx
        assert 'count="1"' in ctx


# ─────────────────────────────────────────────────────────────────
# Unit Tests: format_page_content (detailed)
# ─────────────────────────────────────────────────────────────────

class TestFormatPageContentDetailed:
    """Detailed tests for deep-dive page content formatting."""

    def test_empty_pages(self):
        from prompts.manuals_assistant import format_page_content

        ctx = format_page_content([])
        assert "<page_content>" in ctx
        assert "No page content available" in ctx
        assert "</page_content>" in ctx

    def test_single_page(self):
        from prompts.manuals_assistant import format_page_content

        pages = [
            {
                "content": "Step 1: Remove cover.",
                "filename": "kenr5403-00_testing",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
            }
        ]
        ctx = format_page_content(pages)
        assert "kenr5403-00_testing, Page 48" in ctx
        assert "(3516 | testing)" in ctx
        assert "Step 1: Remove cover." in ctx
        assert "<page_content>" in ctx
        assert "</page_content>" in ctx

    def test_multiple_pages_separator(self):
        from prompts.manuals_assistant import format_page_content

        pages = [
            {
                "content": "Page 48 content",
                "filename": "doc",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
            },
            {
                "content": "Page 49 content",
                "filename": "doc",
                "page_num": 49,
                "equipment": "3516",
                "doc_type": "testing",
            },
        ]
        ctx = format_page_content(pages)
        # Both pages present with separator
        assert "--- doc, Page 48" in ctx
        assert "--- doc, Page 49" in ctx

    def test_content_preserved_verbatim(self):
        from prompts.manuals_assistant import format_page_content

        content = "Torque: 45 ± 5 N·m\nClearance: 0.38 mm"
        pages = [
            {
                "content": content,
                "filename": "doc",
                "page_num": 1,
                "equipment": "3516",
                "doc_type": "testing",
            }
        ]
        ctx = format_page_content(pages)
        assert content in ctx


# ─────────────────────────────────────────────────────────────────
# Unit Tests: build_messages (detailed)
# ─────────────────────────────────────────────────────────────────

class TestBuildMessagesDetailed:
    """Detailed tests for message assembly."""

    def test_system_prompt_contains_context(self):
        from prompts.manuals_assistant import build_messages

        context = '<search_results query="test" count="0">No results.</search_results>'
        system, messages = build_messages(context, [], "my query")
        assert context in system

    def test_system_prompt_starts_with_base(self):
        from prompts.manuals_assistant import build_messages, SYSTEM_PROMPT

        system, _ = build_messages("ctx", [], "q")
        assert system.startswith(SYSTEM_PROMPT)

    def test_query_as_last_message(self):
        from prompts.manuals_assistant import build_messages

        _, messages = build_messages("ctx", [], "user question")
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "user question"

    def test_history_preserved_in_order(self):
        from prompts.manuals_assistant import build_messages

        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "response"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "response2"},
        ]
        _, messages = build_messages("ctx", history, "third")
        assert len(messages) == 5
        assert messages[0]["content"] == "first"
        assert messages[1]["content"] == "response"
        assert messages[4]["content"] == "third"

    def test_empty_history(self):
        from prompts.manuals_assistant import build_messages

        _, messages = build_messages("ctx", [], "hello")
        assert len(messages) == 1

    def test_returns_tuple(self):
        from prompts.manuals_assistant import build_messages

        result = build_messages("ctx", [], "q")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_system_and_context_separated_by_newlines(self):
        from prompts.manuals_assistant import build_messages

        system, _ = build_messages("CONTEXT_HERE", [], "q")
        # Context should be separated from system prompt
        assert "\n\nCONTEXT_HERE" in system

    def test_history_not_mutated(self):
        from prompts.manuals_assistant import build_messages

        history = [{"role": "user", "content": "hello"}]
        original_len = len(history)
        build_messages("ctx", history, "follow up")
        assert len(history) == original_len


# ─────────────────────────────────────────────────────────────────
# Integration Tests: Citation format enforcement
# ─────────────────────────────────────────────────────────────────

class TestCitationFormatEnforcement:
    """Verify the prompt enforces bracket citation format [Doc, p.XX]."""

    def test_prompt_has_correct_format_examples(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Correct examples should use square brackets
        assert "[kenr5403-00_testing-and-adjusting, p.52]" in SYSTEM_PROMPT
        assert "[senr9773-00_3516-troubleshooting, p.112]" in SYSTEM_PROMPT
        assert "[renr2400-00_C18-disassembly, p.88]" in SYSTEM_PROMPT

    def test_prompt_has_wrong_format_examples(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Wrong examples should show what NOT to do
        assert "Page 52 of kenr5403" in SYSTEM_PROMPT
        assert "(kenr5403-00_testing, p.52)" in SYSTEM_PROMPT

    def test_prompt_instructs_never_paren(self):
        from prompts.manuals_assistant import SYSTEM_PROMPT

        # Should explicitly say to use square brackets, not parentheses
        assert "square brackets" in SYSTEM_PROMPT.lower() or "brackets []" in SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────────
# Integration Tests: Context mode selection
# ─────────────────────────────────────────────────────────────────

class TestContextModeSelection:
    """Verify context flows correctly through format → build pipeline."""

    def test_triage_mode_pipeline(self):
        from prompts.manuals_assistant import (
            format_search_results, build_messages
        )

        results = [
            {
                "filename": "doc.pdf",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
                "snippet": "valve lash",
                "authority": "primary",
                "score": 1.0,
            }
        ]
        context = format_search_results(results, "valve lash", equipment="3516")
        system, messages = build_messages(context, [], "valve lash 3516")

        assert "<search_results" in system
        assert "valve lash" in system
        assert messages[-1]["content"] == "valve lash 3516"

    def test_deep_dive_mode_pipeline(self):
        from prompts.manuals_assistant import (
            format_page_content, build_messages
        )

        pages = [
            {
                "content": "Step 1: Remove cover. Step 2: Measure.",
                "filename": "doc.pdf",
                "page_num": 48,
                "equipment": "3516",
                "doc_type": "testing",
            }
        ]
        context = format_page_content(pages)
        system, messages = build_messages(
            context,
            [{"role": "user", "content": "valve lash"},
             {"role": "assistant", "content": "Found results."}],
            "walk me through page 48"
        )

        assert "<page_content>" in system
        assert "Step 1: Remove cover." in system
        assert len(messages) == 3
