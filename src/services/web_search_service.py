"""Web Search Service stub."""

from typing import Optional

_service = None


def get_web_search_service():
    return _service


def create_web_search_service(app):
    global _service
    if app.config.get("TAVILY_API_KEY"):
        _service = True  # Just a truthy stub
    return _service
