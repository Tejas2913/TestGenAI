"""Abstract Base Class for Mutation Operators in TestGen AI v2.2.

Defines the MutationOperator interface following the Open/Closed Principle.
Each concrete operator subclass is responsible for ONE mutation family only.
"""

from abc import ABC, abstractmethod
import ast
from app.domain.mutation import MutationCategory


class MutationOperator(ABC):
    """Abstract interface for isolated AST code mutation operator strategies."""

    __test__ = False

    @property
    @abstractmethod
    def operator_name(self) -> str:
        """Return the unique name identifier of the mutation operator."""
        raise NotImplementedError

    @property
    @abstractmethod
    def category(self) -> MutationCategory:
        """Return the MutationCategory enum classification for this operator."""
        raise NotImplementedError

    @property
    @abstractmethod
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        """Return tuple of AST node classes supported by this mutation operator."""
        raise NotImplementedError

    @abstractmethod
    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        """Generate list of (mutated_ast_node, mutation_description) tuples for a target node."""
        raise NotImplementedError
