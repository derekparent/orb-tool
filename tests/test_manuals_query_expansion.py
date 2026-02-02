import pytest

from services import manuals_service


@pytest.mark.parametrize("query", ['"valve lash"', "valve AND lash", "turbo*"])
def test_prepare_search_query_skips_advanced_syntax(query: str) -> None:
    assert manuals_service.prepare_search_query(query) == query


def test_prepare_search_query_expands_acronyms() -> None:
    expanded = manuals_service.prepare_search_query("TDC procedure")
    assert "top dead center" in expanded
    assert expanded.startswith("(TDC procedure) OR (")


def test_prepare_search_query_expands_spelling_variants() -> None:
    expanded = manuals_service.prepare_search_query("cooland leak")
    assert "coolant" in expanded


def test_prepare_search_query_adds_phrase_boost() -> None:
    expanded = manuals_service.prepare_search_query("fuel filter")
    assert '"fuel filter"' in expanded


def test_prepare_search_query_expands_synonyms() -> None:
    expanded = manuals_service.prepare_search_query("turbo inspection")
    assert "turbocharger" in expanded
