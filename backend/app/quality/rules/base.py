"""TestGen AI v2.3 — Base Quality Rule Framework

Abstract Base Class defining the contract for quality metrics and diagnostic rules.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import structlog

logger = structlog.get_logger()


class BaseQualityRule(ABC):
    """Abstract base class for quality evaluation rules."""

    def __init__(self, rule_name: str, weight: float = 1.0) -> None:
        self.rule_name = rule_name
        self.weight = weight
        self.logger = logger.bind(rule=rule_name)

    @abstractmethod
    def evaluate(self, test_code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate quality rule against candidate test code.

        Args:
            test_code: Pytest test suite code string.
            context: Execution and quality evaluation context metadata.

        Returns:
            Diagnostic outcome dictionary.
        """
        pass
