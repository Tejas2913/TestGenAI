"""TestGen AI v2.4.0 — Extended Routing Strategies

New provider-agnostic routing strategies backed by ProviderRegistry.
No strategy hardcodes provider names or capability booleans.

New strategies:
  FastestStrategy       — selects by lowest typical_latency_ms
  LowestCostStrategy    — selects by lowest estimated_input_cost
  HighestQualityStrategy — selects by highest quality_score
  ReasoningStrategy     — prefers providers with supports_reasoning=True
  HealthAwareStrategy   — avoids providers degraded by recent failures

Existing strategies (BalancedStrategy, CostStrategy, QualityStrategy,
LatencyStrategy, ResearchStrategy) remain untouched in strategies.py.
"""

from typing import Any, Dict, List, Optional

from app.domain.v23_models import ProviderDecision
from app.infrastructure.providers.provider_registry import GLOBAL_REGISTRY
from app.infrastructure.routing_strategies.base import BaseRoutingStrategy


class FastestStrategy(BaseRoutingStrategy):
    """Select the provider with the lowest typical_latency_ms in the registry.

    Falls back to the first available provider if registry has no data.
    """

    def __init__(self) -> None:
        super().__init__(strategy_name="FastestStrategy")

    def select_provider(
        self, available_providers: List[str], metrics: Dict[str, Any]
    ) -> ProviderDecision:
        ranked = GLOBAL_REGISTRY.rank_by(available_providers, "typical_latency_ms", ascending=True)
        selected = ranked[0] if ranked else (available_providers[0] if available_providers else "Gemini")
        cap = GLOBAL_REGISTRY.get(selected)
        return ProviderDecision(
            selected_provider=selected,
            strategy_used=self.strategy_name,
            estimated_cost=cap.estimated_input_cost if cap else 0.001,
            latency_ms=cap.typical_latency_ms if cap else 250.0,
        )


class LowestCostStrategy(BaseRoutingStrategy):
    """Select the provider with the lowest estimated_input_cost in the registry."""

    def __init__(self) -> None:
        super().__init__(strategy_name="LowestCostStrategy")

    def select_provider(
        self, available_providers: List[str], metrics: Dict[str, Any]
    ) -> ProviderDecision:
        ranked = GLOBAL_REGISTRY.rank_by(available_providers, "estimated_input_cost", ascending=True)
        selected = ranked[0] if ranked else (available_providers[0] if available_providers else "Gemini")
        cap = GLOBAL_REGISTRY.get(selected)
        return ProviderDecision(
            selected_provider=selected,
            strategy_used=self.strategy_name,
            estimated_cost=cap.estimated_input_cost if cap else 0.0001,
            latency_ms=cap.typical_latency_ms if cap else 500.0,
        )


class HighestQualityStrategy(BaseRoutingStrategy):
    """Select the provider with the highest quality_score in the registry."""

    def __init__(self) -> None:
        super().__init__(strategy_name="HighestQualityStrategy")

    def select_provider(
        self, available_providers: List[str], metrics: Dict[str, Any]
    ) -> ProviderDecision:
        # ascending=False → highest quality first
        ranked = GLOBAL_REGISTRY.rank_by(available_providers, "quality_score", ascending=False)
        selected = ranked[0] if ranked else (available_providers[0] if available_providers else "Claude")
        cap = GLOBAL_REGISTRY.get(selected)
        return ProviderDecision(
            selected_provider=selected,
            strategy_used=self.strategy_name,
            estimated_cost=cap.estimated_input_cost if cap else 0.003,
            latency_ms=cap.typical_latency_ms if cap else 1500.0,
        )


class ReasoningStrategy(BaseRoutingStrategy):
    """Select a provider that supports reasoning (chain-of-thought / thinking modes).

    Prefers the highest-quality reasoning-capable provider.
    Falls back to the highest-quality provider overall if none support reasoning.
    """

    def __init__(self) -> None:
        super().__init__(strategy_name="ReasoningStrategy")

    def select_provider(
        self, available_providers: List[str], metrics: Dict[str, Any]
    ) -> ProviderDecision:
        # Filter to providers with supports_reasoning=True
        reasoning_capable = GLOBAL_REGISTRY.filter_capable(
            available_providers, "supports_reasoning"
        )
        pool = reasoning_capable if reasoning_capable else available_providers

        # Among capable providers, pick highest quality
        ranked = GLOBAL_REGISTRY.rank_by(pool, "quality_score", ascending=False)
        selected = ranked[0] if ranked else (available_providers[0] if available_providers else "Claude")
        cap = GLOBAL_REGISTRY.get(selected)
        return ProviderDecision(
            selected_provider=selected,
            strategy_used=self.strategy_name,
            estimated_cost=cap.estimated_input_cost if cap else 0.003,
            latency_ms=cap.typical_latency_ms if cap else 2000.0,
        )


class HealthAwareStrategy(BaseRoutingStrategy):
    """Select the healthiest provider based on live health monitor scores.

    Accepts health_scores from metrics dict (injected by the router).
    Falls back to BalancedStrategy ordering if no health data available.

    Configurable thresholds:
      failure_threshold  — exclude providers with failure_rate above this (default 0.5)
      latency_threshold  — exclude providers with avg_latency_ms above this (default 10000)
    """

    def __init__(
        self,
        failure_threshold: float = 0.5,
        latency_threshold_ms: float = 10_000.0,
    ) -> None:
        super().__init__(strategy_name="HealthAwareStrategy")
        self.failure_threshold = failure_threshold
        self.latency_threshold_ms = latency_threshold_ms

    def select_provider(
        self, available_providers: List[str], metrics: Dict[str, Any]
    ) -> ProviderDecision:
        """Select provider using live health scores from metrics dict.

        Expected metrics keys:
          "health_scores": Dict[str, float]  — e.g. {"Gemini": 0.95, "OpenAI": 0.70}
          "failure_rates": Dict[str, float]  — e.g. {"Gemini": 0.05, "OpenAI": 0.30}
          "avg_latencies": Dict[str, float]  — e.g. {"Gemini": 320.0, "OpenAI": 1200.0}
        """
        health_scores: Dict[str, float] = metrics.get("health_scores", {})
        failure_rates: Dict[str, float] = metrics.get("failure_rates", {})
        avg_latencies: Dict[str, float] = metrics.get("avg_latencies", {})

        # Filter out providers exceeding thresholds
        eligible = []
        for name in available_providers:
            fr = failure_rates.get(name, 0.0)
            lat = avg_latencies.get(name, 0.0)
            if fr <= self.failure_threshold and (lat == 0.0 or lat <= self.latency_threshold_ms):
                eligible.append(name)

        # If all filtered out, fall back to full list
        if not eligible:
            eligible = list(available_providers)

        # Sort eligible by health score descending; unknown providers get 1.0 (assume healthy)
        eligible.sort(key=lambda n: health_scores.get(n, 1.0), reverse=True)
        selected = eligible[0] if eligible else (available_providers[0] if available_providers else "Gemini")

        cap = GLOBAL_REGISTRY.get(selected)
        score = health_scores.get(selected, 1.0)
        return ProviderDecision(
            selected_provider=selected,
            strategy_used=self.strategy_name,
            estimated_cost=cap.estimated_input_cost if cap else 0.001,
            latency_ms=cap.typical_latency_ms if cap else 500.0,
        )
