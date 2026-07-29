"""Mutation Operators Package for TestGen AI v2.2."""

from app.services.mutation_operators.arithmetic_operator import ArithmeticOperator
from app.services.mutation_operators.base_operator import MutationOperator
from app.services.mutation_operators.boolean_operator import BooleanOperator
from app.services.mutation_operators.comparison_operator import ComparisonOperator
from app.services.mutation_operators.constant_replacement import ConstantReplacementOperator
from app.services.mutation_operators.return_value import ReturnValueOperator
from app.services.mutation_operators.unary_operator import UnaryOperator

DEFAULT_MUTATION_OPERATORS: list[MutationOperator] = [
    ComparisonOperator(),
    BooleanOperator(),
    ArithmeticOperator(),
    UnaryOperator(),
    ConstantReplacementOperator(),
    ReturnValueOperator(),
]

__all__ = [
    "MutationOperator",
    "ComparisonOperator",
    "BooleanOperator",
    "ArithmeticOperator",
    "UnaryOperator",
    "ConstantReplacementOperator",
    "ReturnValueOperator",
    "DEFAULT_MUTATION_OPERATORS",
]
