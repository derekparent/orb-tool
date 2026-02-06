"""
LLM Service — Anthropic SDK wrapper for the Manuals Assistant.

Sync-only (Flask is sync). Handles retries, streaming, and basic cost tracking.
If you ever swap providers, refactor this one file.
"""

import logging
import time
from collections.abc import Iterator
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when the LLM service encounters an error."""


class LLMService:
    """Thin wrapper around the Anthropic Python SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5-20250929",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        if not api_key:
            raise LLMServiceError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.max_retries = max_retries
        # Simple cost tracking (per-session, not persisted)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> str:
        """Send a message and return the full response text.

        Args:
            system: System prompt (includes RAG context)
            messages: Conversation messages
            max_tokens: Max tokens in response

        Returns:
            Response text

        Raises:
            LLMServiceError on failure after retries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                )
                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens
                return response.content[0].text

            except anthropic.RateLimitError:
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt})")
                    time.sleep(wait)
                    continue
                raise LLMServiceError("Rate limited by Anthropic API after retries")

            except anthropic.APIStatusError as e:
                if attempt < self.max_retries and e.status_code >= 500:
                    wait = 2 ** attempt
                    logger.warning(f"API error {e.status_code}, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise LLMServiceError(f"Anthropic API error: {e.message}")

            except anthropic.APIConnectionError as e:
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning(f"Connection error, retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise LLMServiceError(f"Cannot reach Anthropic API: {e}")

        raise LLMServiceError("Max retries exceeded")

    def stream(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> Iterator[str]:
        """Stream response tokens as they arrive.

        Yields individual text delta strings. The caller is responsible
        for assembling these into the full response.

        Raises:
            LLMServiceError on failure
        """
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text

                # Update token counts from final message
                response = stream.get_final_message()
                self.total_input_tokens += response.usage.input_tokens
                self.total_output_tokens += response.usage.output_tokens

        except anthropic.RateLimitError:
            raise LLMServiceError("Rate limited by Anthropic API")
        except anthropic.APIStatusError as e:
            raise LLMServiceError(f"Anthropic API error: {e.message}")
        except anthropic.APIConnectionError as e:
            raise LLMServiceError(f"Cannot reach Anthropic API: {e}")

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a simple heuristic (~4 chars per token) since the Anthropic
        SDK doesn't expose a standalone tokenizer. Good enough for budget
        management.
        """
        return len(text) // 4

    @property
    def cost_summary(self) -> dict:
        """Return cumulative token usage for this service instance."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
        }


# Module-level singleton, initialized by create_llm_service()
_service: Optional[LLMService] = None


def create_llm_service(app) -> Optional[LLMService]:
    """Initialize the LLM service from Flask app config.

    Returns None if API key is not configured (graceful degradation).
    """
    global _service
    api_key = app.config.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — chat assistant disabled")
        return None

    _service = LLMService(
        api_key=api_key,
        model=app.config.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
        timeout=app.config.get("CHAT_TIMEOUT", 30),
    )
    return _service


def get_llm_service() -> Optional[LLMService]:
    """Get the module-level LLM service instance."""
    return _service
