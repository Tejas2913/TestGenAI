"""Routing strategies module for TestGen AI v2.3 / v2.4."""

from app.infrastructure.routing_strategies.base import BaseRoutingStrategy
from app.infrastructure.routing_strategies.strategies import (
    BalancedStrategy,
    CostStrategy,
    LatencyStrategy,
    QualityStrategy,
    ResearchStrategy,
)
from app.infrastructure.routing_strategies.extended_strategies import (
    FastestStrategy,
    HighestQualityStrategy,
    HealthAwareStrategy,
    LowestCostStrategy,
    ReasoningStrategy,
)

__all__ = [
    # v2.3 strategies
    "BalancedStrategy",
    "BaseRoutingStrategy",
    "CostStrategy",
    "LatencyStrategy",
    "QualityStrategy",
    "ResearchStrategy",
    # v2.4 strategies
    "FastestStrategy",
    "HealthAwareStrategy",
    "HighestQualityStrategy",
    "LowestCostStrategy",
    "ReasoningStrategy",
]
