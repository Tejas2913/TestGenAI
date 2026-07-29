"""Boolean Operator Mutation Strategy for TestGen AI v2.2."""

import ast
import copy
from app.domain.mutation import MutationCategory
from app.services.mutation_operators.base_operator import MutationOperator


class BooleanOperator(MutationOperator):
    """Mutates logical boolean operators (and ↔ or)."""

    __test__ = False

    @property
    def operator_name(self) -> str:
        return "BOOLEAN_OPERATOR"

    @property
    def category(self) -> MutationCategory:
        return MutationCategory.BINARY_OPERATOR

    @property
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        return (ast.BoolOp,)

    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        if not isinstance(node, ast.BoolOp):
            return []

        results: list[tuple[ast.AST, str]] = []
        if isinstance(node.op, ast.And):
            mutated_node = copy.deepcopy(node)
            mutated_node.op = ast.Or()
            results.append((mutated_node, "Replaced 'and' with 'or'"))
        elif isinstance(node.op, ast.Or):
            mutated_node = copy.deepcopy(node)
            mutated_node.op = ast.And()
            results.append((mutated_node, "Replaced 'or' with 'and'"))

        return results
