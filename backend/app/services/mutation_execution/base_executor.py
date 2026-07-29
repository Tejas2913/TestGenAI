"""Abstract Base Class for Mutation Execution Strategies in TestGen AI v2.2.

Defines the MutationExecutor interface following Strategy pattern & SOLID principles.
Decouples mutation generation from execution backends.
"""

from abc import ABC, abstractmethod
from typing import Any
from app.domain.mutation import MutantResult, MutationSummary


class MutationExecutor(ABC):
    """Abstract interface for decoupled mutation execution backends."""

    __test__ = False

    @property
    @abstractmethod
    def executor_name(self) -> str:
        """Return unique name identifier of execution strategy."""
        raise NotImplementedError

    @abstractmethod
    def supports_environment(self) -> bool:
        """Check whether execution environment is available and operational."""
        raise NotImplementedError

    @abstractmethod
    def execute_mutant(
        self,
        mutant: MutantResult,
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
        timeout_seconds: int = 15,
    ) -> MutantResult:
        """Execute test suite against a single mutated source code variant."""
        raise NotImplementedError

    @abstractmethod
    def execute_campaign(
        self,
        mutants: list[MutantResult],
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
        timeout_seconds: int = 15,
    ) -> MutationSummary:
        """Execute mutation testing campaign across a list of generated mutants."""
        raise NotImplementedError
