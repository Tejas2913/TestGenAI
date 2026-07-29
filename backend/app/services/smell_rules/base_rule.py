"""Abstract Base Class for Test Smell Rules in TestGen AI v2.2.

Defines the TestSmellRule interface following the Open/Closed Principle.
"""

from abc import ABC, abstractmethod
import ast
from app.domain.test_smell import TestSmellDiagnostic


class TestSmellRule(ABC):
    """Abstract interface for isolated static test smell detection rules."""

    __test__ = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name identifier of the smell rule."""
        raise NotImplementedError

    @property
    @abstractmethod
    def severity(self) -> str:
        """Return the default severity level of the smell rule (LOW, MEDIUM, HIGH)."""
        raise NotImplementedError

    @abstractmethod
    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        """Detect smell occurrences within a test function AST node."""
        raise NotImplementedError
