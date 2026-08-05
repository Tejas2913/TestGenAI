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
def normalize_payload(payload: Any) -> PromptPayload:
    """Centralized backward-compatibility adapter for PromptPayload contracts.

    Normalizes any supported PromptPayload object or dictionary into a
    v2.3/v2.4 PromptPayload dataclass instance.

    Supported Contracts:
      1. v2.3 / v2.4 PromptPayload (dataclass with rendered_system, rendered_user)
      2. Legacy / V1 PromptPayload (Pydantic model or object with system_prompt, developer_prompt, user_prompt)
      3. Dict matching either format

    Raises:
      ValueError: If payload is None or neither supported contract is satisfied with valid content.
    """
    if payload is None:
        raise ValueError("PromptPayload cannot be None.")

    # 1. Pass-through for existing v2.3/v2.4 PromptPayload dataclasses
    if isinstance(payload, PromptPayload):
        if not payload.rendered_system and not payload.rendered_user:
            raise ValueError("PromptPayload missing prompt content: rendered_system and rendered_user are empty.")
        return payload

    def get_val(key: str, default: Any = None) -> Any:
        if isinstance(payload, dict):
            return payload.get(key, default)
        return getattr(payload, key, default)

    rendered_system = get_val("rendered_system")
    rendered_user = get_val("rendered_user")
    system_prompt = get_val("system_prompt")
    developer_prompt = get_val("developer_prompt")
    user_prompt = get_val("user_prompt")

    # Contract A: v2.3 / v2.4 fields explicitly present
    if rendered_system is not None or rendered_user is not None:
        sys_str = str(rendered_system or "").strip()
        usr_str = str(rendered_user or "").strip()
        if not sys_str and not usr_str:
            raise ValueError("PromptPayload missing prompt content: rendered_system and rendered_user are empty.")

    # Contract B: Legacy / V1 fields present
    elif system_prompt is not None or user_prompt is not None:
        sys_parts = []
        if system_prompt:
            sys_parts.append(str(system_prompt).strip())
        if developer_prompt:
            sys_parts.append(str(developer_prompt).strip())

        sys_str = "\n\n".join(sys_parts)
        usr_str = str(user_prompt or "").strip()

        if not sys_str and not usr_str:
            raise ValueError("PromptPayload missing prompt content: system_prompt and user_prompt are empty.")

    else:
        raise ValueError(
            "Unsupported PromptPayload contract. Must contain either "
            "(rendered_system, rendered_user) or (system_prompt, user_prompt)."
        )

    agent_name = str(get_val("agent_name") or "generator")
    template_name = str(get_val("template_name") or "default")
    version = str(get_val("version") or "v2.4")
    prompt_version = str(get_val("prompt_version") or "v1")

    # Token estimation: use provided if positive, else compute from char length
    raw_tokens = get_val("estimated_tokens")
    if raw_tokens is not None and isinstance(raw_tokens, int) and raw_tokens > 0:
        estimated_tokens = raw_tokens
    else:
        total_chars = len(sys_str) + len(usr_str)
        estimated_tokens = max(1, total_chars // 4)

    metadata = get_val("metadata") or {}

    return PromptPayload(
        template_name=template_name,
        rendered_system=sys_str,
        rendered_user=usr_str,
        version=version,
        agent_name=agent_name,
        repository_summary=str(get_val("repository_summary") or ""),
        prompt_version=prompt_version,
        estimated_tokens=estimated_tokens,
        metadata=metadata,
    )


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
        prompt_payload: Any,
        strategy: Optional[BaseRoutingStrategy] = None,
        options: Optional[Dict] = None,
        workflow_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ProviderResponse:
        """Route and execute PromptPayload through optimal provider with failover.

        v2.4 enhancements over v2.3:
          - Centralized PromptPayload normalization (legacy V1 & v2.3/v2.4 supported)
          - Health scores are injected into strategy metrics
          - ProviderFailoverManager handles retry + backoff
          - HealthMonitor and CostTracker are updated after every invocation

        Args:
            prompt_payload: Legacy V1 or v2.3/v2.4 PromptPayload or dict.
            strategy: Optional routing strategy override.
            options: Optional runtime options.
            workflow_id: For log correlation and cost tracking.
            request_id: For log correlation.

        Returns:
            Unified ProviderResponse model.

        Raises:
            ProviderUnavailableError: If all providers + retries are exhausted.
            ValueError: If prompt_payload contract is invalid/malformed.
        """
        # 0. Normalize payload to v2.3/v2.4 contract
        prompt_payload = normalize_payload(prompt_payload)

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
    # generate() — LLMProvider compatibility shim (for GenerationService)
    # ------------------------------------------------------------------

    def generate(self, payload: Any, options: Optional[Dict] = None) -> str:
        """Drop-in replacement for LLMProvider.generate() with automatic failover.

        Accepts both Legacy/V1 and v2.3/v2.4 PromptPayloads.  Normalizes payload
        at boundary and routes through execute_prompt() for full failover, health
        monitoring, and cost tracking.

        Args:
            payload: Legacy V1 or v2.3/v2.4 PromptPayload or dict.
            options: Optional runtime options.

        Returns:
            Raw LLM response string (same contract as GeminiProvider.generate).
        """
        norm_payload = normalize_payload(payload)
        response = self.execute_prompt(prompt_payload=norm_payload, options=options)
        self.last_usage = {
            "input_tokens": response.prompt_tokens,
            "output_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens,
        }
        return response.response_text

    # ------------------------------------------------------------------
    # Streaming execute (v2.4 new)
    # ------------------------------------------------------------------

    def stream_execute_prompt(
        self,
        prompt_payload: Any,
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

        # Normalize payload
        prompt_payload = normalize_payload(prompt_payload)

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
