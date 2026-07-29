"""Return Value Swap Mutation Strategy for TestGen AI v2.2."""

import ast
import copy
from app.domain.mutation import MutationCategory
from app.services.mutation_operators.base_operator import MutationOperator


class ReturnValueOperator(MutationOperator):
    """Mutates return statements (return True ↔ return False)."""

    __test__ = False

    @property
    def operator_name(self) -> str:
        return "RETURN_VALUE_SWAP"

    @property
    def category(self) -> MutationCategory:
        return MutationCategory.RETURN_VALUE_SWAP

    @property
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        return (ast.Return,)

    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        if not isinstance(node, ast.Return) or node.value is None:
            return []

        val_node = node.value
        if isinstance(val_node, ast.Constant) and isinstance(val_node.value, bool):
            orig_bool = val_node.value
            new_bool = not orig_bool
            mutated_node = copy.deepcopy(node)
            mutated_node.value = ast.Constant(value=new_bool)
            orig_str = "True" if orig_bool else "False"
            new_str = "False" if orig_bool else "True"
            return [(mutated_node, f"Replaced return {orig_str} with return {new_str}")]

        return []
