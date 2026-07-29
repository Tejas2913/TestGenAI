"""Comparison Operator Mutation Strategy for TestGen AI v2.2."""

import ast
import copy
from app.domain.mutation import MutationCategory
from app.services.mutation_operators.base_operator import MutationOperator

SWAP_MAP = {
    ast.Eq: (ast.NotEq, "==" , "!="),
    ast.NotEq: (ast.Eq, "!=", "=="),
    ast.Lt: (ast.LtE, "<", "<="),
    ast.LtE: (ast.Lt, "<=", "<"),
    ast.Gt: (ast.GtE, ">", ">="),
    ast.GtE: (ast.Gt, ">=", ">"),
}


class ComparisonOperator(MutationOperator):
    """Mutates comparison operators (==, !=, <, <=, >, >=)."""

    __test__ = False

    @property
    def operator_name(self) -> str:
        return "COMPARISON_OPERATOR"

    @property
    def category(self) -> MutationCategory:
        return MutationCategory.COMPARISON_OPERATOR

    @property
    def supported_node_types(self) -> tuple[type[ast.AST], ...]:
        return (ast.Compare,)

    def mutate(self, node: ast.AST) -> list[tuple[ast.AST, str]]:
        if not isinstance(node, ast.Compare):
            return []

        results: list[tuple[ast.AST, str]] = []
        for idx, op in enumerate(node.ops):
            op_type = type(op)
            if op_type in SWAP_MAP:
                new_op_cls, orig_str, new_str = SWAP_MAP[op_type]
                mutated_node = copy.deepcopy(node)
                mutated_node.ops[idx] = new_op_cls()
                desc = f"Replaced comparison operator '{orig_str}' with '{new_str}'"
                results.append((mutated_node, desc))

        return results
