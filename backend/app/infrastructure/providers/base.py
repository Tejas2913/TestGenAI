"""TestGen AI v2.3 — Base LLM Provider Framework

Abstract Base Class defining the unified contract for external LLM model providers.
"""

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, Iterator, Optional
import structlog

from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import PromptPayload

logger = structlog.get_logger()


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers (Gemini, Claude, OpenAI, Groq, OpenRouter)."""

    def __init__(
        self,
        provider_name: str,
        model_name: str,
        cost_per_1k_input: float = 0.0015,
        cost_per_1k_output: float = 0.002,
    ) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        self.logger = logger.bind(provider=provider_name, model=model_name)

    def generate(
        self, prompt_payload: PromptPayload, options: Optional[Dict[str, Any]] = None
    ) -> ProviderResponse:
        """Generate a normalized ProviderResponse from a PromptPayload.

        Args:
            prompt_payload: Provider-agnostic PromptPayload containing system/user prompts.
            options: Optional runtime options (temperature, max_tokens, etc.).

        Returns:
            ProviderResponse domain object.
        """
        text = self.generate_text(prompt_payload, options)
        return ProviderResponse(
            provider_name=self.provider_name,
            model_name=self.model_name,
            response_text=text,
        )

    def stream_generate(
        self, prompt_payload: PromptPayload, options: Optional[Dict[str, Any]] = None
    ) -> Iterator:
        """Stream generation yielding StreamChunk objects.

        Default implementation falls back to generate() and wraps the full
        response as a single chunk. Providers that support native streaming
        override this method to yield incremental chunks.

        Args:
            prompt_payload: Provider-agnostic PromptPayload.
            options: Optional runtime options.

        Yields:
            StreamChunk objects. The final chunk has is_final=True.
        """
        from app.infrastructure.providers.streaming import stream_from_response
        response = self.generate(prompt_payload=prompt_payload, options=options)
        yield from stream_from_response(response)

    def generate_text(
        self, prompt: PromptPayload, options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate raw text output from the provider."""
        response = self.generate(prompt_payload=prompt, options=options)
        return response.response_text

    def health_check(self) -> bool:
        """Perform provider health check."""
        return True

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate token expense in USD."""
        cost = (prompt_tokens / 1000.0) * self.cost_per_1k_input + (completion_tokens / 1000.0) * self.cost_per_1k_output
        return round(cost, 6)

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string (1 token ~ 4 chars)."""
        return max(1, len(text) // 4)

    def supports_capability(self, capability: str) -> bool:
        """Check if provider supports a specific capability via the global registry."""
        from app.infrastructure.providers.provider_registry import GLOBAL_REGISTRY
        return GLOBAL_REGISTRY.supports(self.provider_name, capability)
