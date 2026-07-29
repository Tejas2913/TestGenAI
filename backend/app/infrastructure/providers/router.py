"""TestGen AI v2.3 — LLMProviderRouter Implementation

Centralized router coordinating provider evaluation, execution, health monitoring,
and automatic fallback recovery.
"""

from typing import Any, Dict, List, Optional, Union
import structlog

from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import PromptPayload, ProviderDecision
from app.exceptions.v23_exceptions import ProviderError, ProviderUnavailableError
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.claude import ClaudeProvider
from app.infrastructure.providers.evaluator import ProviderEvaluator
from app.infrastructure.providers.gemini import GeminiProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.routing_strategies.base import BaseRoutingStrategy

logger = structlog.get_logger()


class LLMProviderRouter:
    """Intelligent Multi-LLM Provider Router with automatic fallback recovery."""

    def __init__(
        self,
        evaluator: Optional[ProviderEvaluator] = None,
        provider_evaluator: Optional[ProviderEvaluator] = None,
        mock_mode: bool = True,
    ) -> None:
        self.evaluator = evaluator or provider_evaluator or ProviderEvaluator()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self.logger = logger.bind(component="LLMProviderRouter")

        # Register default concrete providers in mock mode or live env
        self.register_provider(GeminiProvider(mock_mode=mock_mode))
        self.register_provider(OpenAIProvider(mock_mode=mock_mode))
        self.register_provider(ClaudeProvider(mock_mode=mock_mode))

    @property
    def providers(self) -> Dict[str, BaseLLMProvider]:
        """Backward compatibility property returning registered providers dictionary."""
        return self._providers

    def register_provider(
        self,
        provider_or_name: Any,
        provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        """Register a provider instance into the router."""
        if isinstance(provider_or_name, str) and provider is not None:
            target_provider = provider
            name = provider_or_name
        elif isinstance(provider_or_name, BaseLLMProvider):
            target_provider = provider_or_name
            name = provider_or_name.provider_name
        else:
            return

        self._providers[name] = target_provider
        self.logger.info("provider_registered", name=name, model=target_provider.model_name)

    def get_provider(self, name: str) -> BaseLLMProvider:
        """Fetch registered provider instance by name."""
        provider = self._providers.get(name)
        if not provider:
            raise ProviderUnavailableError("Router", f"Provider '{name}' is not registered.")
        return provider

    def execute_prompt(
        self,
        prompt_payload: PromptPayload,
        strategy: Optional[BaseRoutingStrategy] = None,
        options: Optional[Dict] = None,
    ) -> ProviderResponse:
        """Route and execute PromptPayload through optimal provider with automatic fallback.

        Args:
            prompt_payload: Rendered PromptPayload context.
            strategy: Optional routing strategy override.
            options: Optional runtime options.

        Returns:
            Unified ProviderResponse model.

        Raises:
            ProviderUnavailableError: If all providers fail.
        """
        # 1. Evaluate & select optimal provider
        decision: ProviderDecision = self.evaluator.evaluate_and_select(
            providers=self._providers,
            prompt_payload=prompt_payload,
            strategy=strategy,
        )

        selected_name = decision.selected_provider
        attempt_order = [selected_name] + [p for p in self._providers.keys() if p != selected_name]

        last_exception: Optional[Exception] = None

        # 2. Execute with automatic fallback
        for provider_name in attempt_order:
            provider = self._providers.get(provider_name)
            if not provider or not provider.health_check():
                continue

            try:
                self.logger.info(
                    "executing_provider_prompt",
                    provider=provider_name,
                    agent=prompt_payload.agent_name,
                    estimated_tokens=prompt_payload.estimated_tokens,
                )
                response = provider.generate(prompt_payload=prompt_payload, options=options)
                
                self.logger.info(
                    "provider_execution_succeeded",
                    provider=provider_name,
                    latency_ms=response.latency_ms,
                    cost=response.estimated_cost,
                )
                return response

            except ProviderError as pe:
                last_exception = pe
                self.logger.warning(
                    "provider_execution_failed_fallback_triggered",
                    failed_provider=provider_name,
                    error=str(pe),
                )
            except Exception as exc:
                last_exception = exc
                self.logger.error(
                    "unexpected_provider_failure_fallback_triggered",
                    failed_provider=provider_name,
                    error=str(exc),
                )

        # If all providers fail
        raise ProviderUnavailableError(
            "Router", f"All providers failed execution. Last error: {last_exception}"
        ) from last_exception
