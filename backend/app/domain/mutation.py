"""Mutation Analysis Domain Models and Provider Abstraction for TestGen AI v2.2.

Provides domain entities representing individual mutation test results, aggregated
mutation summaries, and the abstract MutationProvider interface for strategy decoupling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MutationCategory(StrEnum):
    """Categories of AST code mutations applied to source code."""

    BINARY_OPERATOR = "BINARY_OPERATOR"
    COMPARISON_OPERATOR = "COMPARISON_OPERATOR"
    UNARY_OPERATOR = "UNARY_OPERATOR"
    CONSTANT_REPLACEMENT = "CONSTANT_REPLACEMENT"
    STATEMENT_DELETION = "STATEMENT_DELETION"
    RETURN_VALUE_SWAP = "RETURN_VALUE_SWAP"


@dataclass
class MutantResult:
    """Execution outcome of a single mutated code variant."""

    mutant_id: str
    category: MutationCategory
    description: str
    original_line: int
    mutated_line_content: str
    status: str
    killing_test: str | None = None
    execution_time_ms: float = 0.0


@dataclass
class MutationSummary:
    """Aggregated summary metrics of a completed mutation testing pass."""

    total_mutants: int = 0
    killed_mutants: int = 0
    survived_mutants: int = 0
    timeout_mutants: int = 0
    incompatible_mutants: int = 0
    mutation_score_pct: float = 0.0
    duration_ms: float = 0.0
    mutants: list[MutantResult] = field(default_factory=list)


class MutationProvider(ABC):
    """Abstract Base Class for pluggable mutation provider strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name identifier of the mutation provider."""
        raise NotImplementedError

    @abstractmethod
    def generate_mutants(self, source_code: str) -> list[Any]:
        """Generate candidate mutation definitions from source code."""
        raise NotImplementedError

    @abstractmethod
    def execute_mutation_pass(
        self,
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
    ) -> MutationSummary:
        """Execute mutation testing pass and return an aggregated MutationSummary."""
        raise NotImplementedError
