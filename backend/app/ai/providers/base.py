"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod

from app.domain.prompt_payload import PromptPayload


class LLMProvider(ABC):
    """Base class for all LLM provider implementations.

    Concrete providers (GeminiProvider, OpenAIProvider, etc.)
    must implement the generate method.
    """

    @abstractmethod
    def generate(self, payload: PromptPayload) -> str:
        """Send a prompt payload to the LLM and return the raw response text.

        Args:
            payload: The assembled system, developer, and user prompts.

        Returns:
            Raw text response from the LLM. No parsing or validation
            is performed at this layer.
        """
        ...
