"""TestGen AI v2.4.0 — LLMProviderRouter (Enterprise Edition)

Centralized router coordinating:
  - Capability-aware provider selection (ProviderRegistry)
  - Health-aware routing (ProviderHealthMonitor)
  - Intelligent retry + failover (ProviderFailoverManager)
  - Cost tracking (ProviderCostTracker)
  - All 5 providers: Gemini, OpenAI, Claude, Groq, OpenRouter

Backward-compatible: execute_prompt() signature unchanged.
"""

from typing import Any, Dict, Iterator, List, Optional
import structlog

from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import PromptPayload, ProviderDecision
from app.exceptions.v23_exceptions import ProviderError, ProviderUnavailableError
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.claude import ClaudeProvider
from app.infrastructure.providers.cost_tracker import ProviderCostTracker
from app.infrastructure.providers.evaluator import ProviderEvaluator
from app.infrastructure.providers.failover import ProviderFailoverManager
from app.infrastructure.providers.gemini import GeminiProvider
from app.infrastructure.providers.groq_provider import GroqProvider
from app.infrastructure.providers.health_monitor import ProviderHealthMonitor
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.providers.openrouter_provider import OpenRouterProvider
from app.infrastructure.providers.provider_registry import GLOBAL_REGISTRY
from app.infrastructure.routing_strategies.base import BaseRoutingStrategy

logger = structlog.get_logger()


class LLMProviderRouter:
    """Enterprise-grade Multi-LLM Provider Router.

    Features (v2.4):
      - ProviderRegistry-driven capability filtering
      - ProviderHealthMonitor for live health scoring
      - ProviderFailoverManager with exponential backoff retry
      - ProviderCostTracker for per-request / daily / monthly cost accounting
      - stream_execute_prompt() for streaming generation
      - Full backward compatibility with v2.3 execute_prompt() interface
    """

    def __init__(
        self,
        evaluator: Optional[ProviderEvaluator] = None,
        provider_evaluator: Optional[ProviderEvaluator] = None,
        mock_mode: Optional[bool] = None,
        # v2.4 enterprise components (optional — defaults created automatically)
        health_monitor: Optional[ProviderHealthMonitor] = None,
        cost_tracker: Optional[ProviderCostTracker] = None,
        failover_manager: Optional[ProviderFailoverManager] = None,
    ) -> None:
        self.evaluator = evaluator or provider_evaluator or ProviderEvaluator()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self.logger = logger.bind(component="LLMProviderRouter")

        # v2.4 enterprise components
        self.health_monitor = health_monitor or ProviderHealthMonitor()
        self.cost_tracker = cost_tracker or ProviderCostTracker()
        self.failover_manager = failover_manager or self._build_failover_manager()

        # Resolve mock_mode: explicit arg > settings.MOCK_MODE > True (safe default)
        if mock_mode is None:
            try:
                from app.core.config import settings
                resolved_mock = settings.MOCK_MODE
            except Exception:
                resolved_mock = True
        else:
            resolved_mock = mock_mode

        # Register all providers from settings
        try:
            from app.core.config import settings as cfg
            self.register_provider(GeminiProvider(
                model_name=cfg.GEMINI_MODEL,
                api_key=cfg.GEMINI_API_KEY,
                mock_mode=resolved_mock,
            ))
            self.register_provider(OpenAIProvider(
                model_name=cfg.OPENAI_MODEL,
                api_key=cfg.OPENAI_API_KEY,
                mock_mode=resolved_mock,
            ))
            self.register_provider(ClaudeProvider(
                model_name=cfg.CLAUDE_MODEL,
                api_key=cfg.ANTHROPIC_API_KEY,
                mock_mode=resolved_mock,
            ))
            self.register_provider(GroqProvider(
                model_name=cfg.GROQ_MODEL,
                api_key=cfg.GROQ_API_KEY,
                mock_mode=resolved_mock,
            ))
            self.register_provider(OpenRouterProvider(
                model_name=cfg.OPENROUTER_MODEL,
                api_key=cfg.OPENROUTER_API_KEY,
                mock_mode=resolved_mock,
            ))
        except Exception:
            # Fallback: defaults if settings unavailable (e.g. unit test isolation)
            self.register_provider(GeminiProvider(mock_mode=resolved_mock))
            self.register_provider(OpenAIProvider(mock_mode=resolved_mock))
            self.register_provider(ClaudeProvider(mock_mode=resolved_mock))
            self.register_provider(GroqProvider(mock_mode=resolved_mock))
            self.register_provider(OpenRouterProvider(mock_mode=resolved_mock))

    def _build_failover_manager(self) -> ProviderFailoverManager:
        """Build FailoverManager from settings or defaults."""
        try:
            from app.core.config import settings
            return ProviderFailoverManager(
                max_retries=getattr(settings, "MAX_PROVIDER_RETRIES", 2),
                base_backoff_ms=200.0,
            )
        except Exception:
            return ProviderFailoverManager(max_retries=2)

    # ------------------------------------------------------------------
    # Registration & lookup
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Core execute (v2.3 compatible + v2.4 enterprise wiring)
    # ------------------------------------------------------------------

    def execute_prompt(
        self,
        prompt_payload: PromptPayload,
        strategy: Optional[BaseRoutingStrategy] = None,
        options: Optional[Dict] = None,
        workflow_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ProviderResponse:
        """Route and execute PromptPayload through optimal provider with failover.

        v2.4 enhancements over v2.3:
          - Health scores are injected into strategy metrics
          - ProviderFailoverManager handles retry + backoff
          - HealthMonitor and CostTracker are updated after every invocation

        Args:
            prompt_payload: Rendered PromptPayload context.
            strategy: Optional routing strategy override.
            options: Optional runtime options.
            workflow_id: For log correlation and cost tracking.
            request_id: For log correlation.

        Returns:
            Unified ProviderResponse model.

        Raises:
            ProviderUnavailableError: If all providers + retries are exhausted.
        """
        # 1. Build health metrics for HealthAwareStrategy
        health_metrics = self._build_health_metrics()

        # 2. Evaluate & select optimal provider
        decision: ProviderDecision = self.evaluator.evaluate_and_select(
            providers=self._providers,
            prompt_payload=prompt_payload,
            strategy=strategy,
            metrics=health_metrics,
        )

        selected_name = decision.selected_provider
        attempt_order = [selected_name] + [
            p for p in self._providers.keys() if p != selected_name
        ]

        # 3. Build ordered provider list (skip health-check failures)
        ordered = [
            self._providers[name]
            for name in attempt_order
            if name in self._providers and self._providers[name].health_check()
        ]

        if not ordered:
            raise ProviderUnavailableError("Router", "No healthy providers available.")

        self.logger.info(
            "executing_provider_prompt",
            provider=selected_name,
            agent=prompt_payload.agent_name,
            estimated_tokens=prompt_payload.estimated_tokens,
            strategy=decision.strategy_used,
            workflow_id=workflow_id,
            request_id=request_id,
        )

        # 4. Delegate to FailoverManager (handles retry + backoff + recording)
        response = self.failover_manager.execute_with_fallback(
            ordered_providers=ordered,
            prompt_payload=prompt_payload,
            options=options,
            health_monitor=self.health_monitor,
            cost_tracker=self.cost_tracker,
            workflow_id=workflow_id,
            request_id=request_id,
        )

        self.logger.info(
            "provider_execution_succeeded",
            provider=response.provider_name,
            latency_ms=response.latency_ms,
            cost=response.estimated_cost,
            tokens=response.total_tokens,
            workflow_id=workflow_id,
        )
        return response

    # ------------------------------------------------------------------
    # Streaming execute (v2.4 new)
    # ------------------------------------------------------------------

    def stream_execute_prompt(
        self,
        prompt_payload: PromptPayload,
        strategy: Optional[BaseRoutingStrategy] = None,
        options: Optional[Dict] = None,
        workflow_id: Optional[str] = None,
    ) -> Iterator:
        """Stream-execute a PromptPayload, yielding StreamChunk objects.

        Selects the primary provider via the routing strategy, then delegates
        to provider.stream_generate(). Falls back to execute_prompt() if
        streaming fails.

        Yields:
            StreamChunk objects; the final chunk has is_final=True.
        """
        from app.infrastructure.providers.streaming import stream_from_response

        # Select provider
        health_metrics = self._build_health_metrics()
        decision: ProviderDecision = self.evaluator.evaluate_and_select(
            providers=self._providers,
            prompt_payload=prompt_payload,
            strategy=strategy,
            metrics=health_metrics,
        )
        selected_name = decision.selected_provider
        provider = self._providers.get(selected_name)

        if not provider or not provider.health_check():
            # Fallback to first healthy provider
            provider = next(
                (p for p in self._providers.values() if p.health_check()), None
            )

        if not provider:
            raise ProviderUnavailableError("Router", "No healthy providers available for streaming.")

        self.logger.info(
            "stream_executing_provider_prompt",
            provider=provider.provider_name,
            agent=prompt_payload.agent_name,
            workflow_id=workflow_id,
        )

        try:
            yield from provider.stream_generate(prompt_payload=prompt_payload, options=options)
        except Exception as exc:
            self.logger.warning(
                "stream_generate_failed_falling_back",
                provider=provider.provider_name,
                error=str(exc),
            )
            # Graceful fallback to blocking generate
            response = self.execute_prompt(
                prompt_payload=prompt_payload,
                strategy=strategy,
                options=options,
                workflow_id=workflow_id,
            )
            yield from stream_from_response(response)

    # ------------------------------------------------------------------
    # Analytics & observability
    # ------------------------------------------------------------------

    def get_analytics(self) -> dict:
        """Return combined analytics from HealthMonitor and CostTracker."""
        from datetime import datetime, timezone
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "health": {
                name: summary.__dict__
                for name, summary in self.health_monitor.get_all_summaries().items()
            },
            "cost": self.cost_tracker.get_summary(),
            "registered_providers": sorted(self._providers.keys()),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_health_metrics(self) -> Dict[str, Any]:
        """Build metrics dict for routing strategies (especially HealthAwareStrategy)."""
        health_scores = {}
        failure_rates = {}
        avg_latencies = {}
        for name in self._providers:
            summary = self.health_monitor.get_summary(name)
            health_scores[name] = summary.health_score
            failure_rates[name] = summary.failure_rate
            avg_latencies[name] = summary.average_latency_ms
        return {
            "health_scores": health_scores,
            "failure_rates": failure_rates,
            "avg_latencies": avg_latencies,
        }
