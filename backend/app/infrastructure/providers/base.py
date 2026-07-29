"""TestGen AI v2.3 — Base LLM Provider Framework

Abstract Base Class defining the contract for external LLM model providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import structlog

from app.domain.v23_models import PromptPayload

logger = structlog.get_logger()


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers (Gemini, Claude, OpenAI, Ollama)."""

    def __init__(self, provider_name: str, model_name: str) -> None:
        self.provider_name = provider_name
        self.model_name = model_name
        self.logger = logger.bind(provider=provider_name, model=model_name)

    @abstractmethod
    def generate_text(
        self, prompt: PromptPayload, options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate text output from the provider.

        Args:
            prompt: PromptPayload object containing rendered system/user prompts.
            options: Optional runtime options (temperature, max_tokens, etc.).

        Returns:
            Raw generated string output.
        """
        pass
