"""TestGen AI v2.3 — Base Routing Strategy Framework

Abstract base class defining the strategy contract for LLM provider routing decisions.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import structlog

from app.domain.v23_models import ProviderDecision

logger = structlog.get_logger()


class BaseRoutingStrategy(ABC):
    """Abstract strategy for LLM provider selection."""

    def __init__(self, strategy_name: str) -> None:
        self.strategy_name = strategy_name
        self.logger = logger.bind(strategy=strategy_name)

    @abstractmethod
    def select_provider(
        self, available_providers: List[str], metrics: Dict[str, Any]
    ) -> ProviderDecision:
        """Select the optimal LLM provider based on strategy metrics.

        Args:
            available_providers: List of candidate provider identifiers.
            metrics: Historical latency, cost, and quality statistics.

        Returns:
            ProviderDecision metadata.
        """
        pass
