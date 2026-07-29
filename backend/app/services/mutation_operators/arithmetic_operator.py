"""Arithmetic Operator Mutation Strategy for TestGen AI v2.2."""

import ast
import copy
from app.domain.mutation import MutationCategory
from app.services.mutation_operators.base_operator import MutationOperator

ARITHMETIC_MAP = {
    ast.Add: (ast.Sub, "+", "-"),
    ast.Sub: (ast.Add, "-", "+"),
    ast.Mult: (ast.FloorDiv, "*", "//"),
    ast.FloorDiv: (ast.Mult, "//", "*"),
}


class ArithmeticOperator(MutationOperator):
    """Mutates binary arithmetic operators (+ ↔ -, * ↔ //)."""

    __test__ = False

    @property
    def operator_name(self) -> str:
        return "ARITHMETIC_OPERATOR"

    @property
    def category(self) -> MutationCategory:
        return MutationCategory.BINARY_OPERATOR

    @property
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        return (ast.BinOp,)

    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        if not isinstance(node, ast.BinOp):
            return []

        op_type = type(node.op)
        if op_type in ARITHMETIC_MAP:
            new_op_cls, orig_str, new_str = ARITHMETIC_MAP[op_type]
            mutated_node = copy.deepcopy(node)
            mutated_node.op = new_op_cls()
            desc = f"Replaced arithmetic operator '{orig_str}' with '{new_str}'"
            return [(mutated_node, desc)]

        return []
