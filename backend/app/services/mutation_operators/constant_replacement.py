"""Constant Replacement Mutation Strategy for TestGen AI v2.2."""

import ast
import copy
from app.domain.mutation import MutationCategory
from app.services.mutation_operators.base_operator import MutationOperator


class ConstantReplacementOperator(MutationOperator):
    """Mutates constant literals (True ↔ False, 0 ↔ 1)."""

    __test__ = False

    @property
    def operator_name(self) -> str:
        return "CONSTANT_REPLACEMENT"

    @property
    def category(self) -> MutationCategory:
        return MutationCategory.CONSTANT_REPLACEMENT

    @property
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        return (ast.Constant,)

    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        if not isinstance(node, ast.Constant):
            return []

        val = node.value
        # Handle booleans (note: bool is subclass of int in Python, check bool first!)
        if isinstance(val, bool):
            mutated_node = copy.deepcopy(node)
            mutated_node.value = not val
            orig_str = "True" if val else "False"
            new_str = "False" if val else "True"
            return [(mutated_node, f"Replaced constant boolean {orig_str} with {new_str}")]

        # Handle numeric 0 ↔ 1
        if isinstance(val, int) and val in (0, 1):
            new_val = 1 if val == 0 else 0
            mutated_node = copy.deepcopy(node)
            mutated_node.value = new_val
            return [(mutated_node, f"Replaced constant integer {val} with {new_val}")]

        return []
