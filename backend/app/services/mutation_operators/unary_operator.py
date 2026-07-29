"""Unary Operator Mutation Strategy for TestGen AI v2.2."""

import ast
import copy
from app.domain.mutation import MutationCategory
from app.services.mutation_operators.base_operator import MutationOperator


class UnaryOperator(MutationOperator):
    """Mutates unary operators (removes 'not')."""

    __test__ = False

    @property
    def operator_name(self) -> str:
        return "UNARY_OPERATOR"

    @property
    def category(self) -> MutationCategory:
        return MutationCategory.UNARY_OPERATOR

    @property
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        return (ast.UnaryOp,)

    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        if not isinstance(node, ast.UnaryOp):
            return []

        if isinstance(node.op, ast.Not):
            mutated_node = copy.deepcopy(node.operand)
            return [(mutated_node, "Removed unary 'not' operator")]

        return []
