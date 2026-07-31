"""TestGen AI v2.3 — ProviderEvaluator Implementation

Evaluates provider health, performance metrics, and delegates model selection to routing strategies.
"""

from typing import Any, Dict, List, Optional
import structlog

from app.domain.v23_models import PromptPayload, ProviderDecision
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.routing_strategies.base import BaseRoutingStrategy
from app.infrastructure.routing_strategies.strategies import BalancedStrategy

logger = structlog.get_logger()


class ProviderEvaluator:
    """Evaluates provider health and metrics to select the optimal provider using a RoutingStrategy."""

    def __init__(
        self,
        default_strategy: Optional[BaseRoutingStrategy] = None,
        strategy: Optional[BaseRoutingStrategy] = None,
    ) -> None:
        self.default_strategy = default_strategy or strategy or BalancedStrategy()
        self.logger = logger.bind(component="ProviderEvaluator")

    def evaluate_and_select(
        self,
        providers: Dict[str, BaseLLMProvider],
        prompt_payload: PromptPayload,
        strategy: Optional[BaseRoutingStrategy] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> ProviderDecision:
        """Select optimal provider from active healthy providers.

        Args:
            providers: Registry dictionary mapping provider names to BaseLLMProvider instances.
            prompt_payload: Incoming PromptPayload context.
            strategy: Optional routing strategy override.
            metrics: Optional external metrics (e.g. health scores from HealthMonitor).

        Returns:
            ProviderDecision domain object.
        """
        active_strategy = strategy or self.default_strategy

        # Filter healthy providers
        healthy_providers: List[str] = [
            name for name, provider in providers.items() if provider.health_check()
        ]

        if not healthy_providers:
            self.logger.warning("no_healthy_providers_found", total_registered=len(providers))
            healthy_providers = list(providers.keys())

        # Merge internal metrics with externally provided metrics (health scores etc.)
        combined_metrics: Dict[str, Any] = {
            "prompt_estimated_tokens": prompt_payload.estimated_tokens,
            "agent_name": prompt_payload.agent_name,
        }
        if metrics:
            combined_metrics.update(metrics)

        decision = active_strategy.select_provider(healthy_providers, combined_metrics)
        self.logger.info(
            "provider_selected",
            selected=decision.selected_provider,
            strategy=decision.strategy_used,
        )
        return decision
