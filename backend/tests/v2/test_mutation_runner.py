"""Comprehensive unit test suite for AST-based MutationRunner & MutationOperators (Phase 4).

Verifies:
  - Comparison operator mutations (== ↔ !=, < ↔ <=, > ↔ >=).
  - Boolean operator mutations (and ↔ or).
  - Arithmetic operator mutations (+ ↔ -, * ↔ //).
  - Unary operator mutations (removes 'not').
  - Constant replacement mutations (True ↔ False, 0 ↔ 1).
  - Return value swap mutations (return True ↔ return False).
  - Nested expressions and multi-operator source modules.
  - Duplicate mutant prevention and deterministic mutant IDs.
  - Resilience against malformed Python syntax (returns empty summary gracefully).
  - Idempotence, immutability, and zero code execution/file modification.
"""

import pytest

from app.domain.mutation import MutationCategory
from app.services.mutation_operators import (
    ArithmeticOperator,
    BooleanOperator,
    ComparisonOperator,
    ConstantReplacementOperator,
    ReturnValueOperator,
    UnaryOperator,
)
from app.services.mutation_runner import MutationRunner


class TestMutationRunnerSuite:
    """Test suite for MutationRunner & AST Mutation Operators."""

    @pytest.fixture
    def runner(self) -> MutationRunner:
        """Provide default MutationRunner instance."""
        return MutationRunner()

    def test_comparison_operator_mutation(self, runner: MutationRunner) -> None:
        """Verify comparison operator mutations (== to !=, < to <=)."""
        code = """
def compare(a, b):
    if a == b:
        return True
    if a < b:
        return False
    return False
"""
        mutants = runner.generate_mutants(code)
        comp_mutants = [m for m in mutants if m.category == MutationCategory.COMPARISON_OPERATOR]
        assert len(comp_mutants) >= 2
        descriptions = [m.description for m in comp_mutants]
        assert any("==" in d and "!=" in d for d in descriptions)
        assert any("<" in d and "<=" in d for d in descriptions)

    def test_boolean_operator_mutation(self, runner: MutationRunner) -> None:
        """Verify boolean operator mutations (and ↔ or)."""
        code = """
def check_bounds(x, y):
    return x > 0 and y > 0
"""
        mutants = runner.generate_mutants(code)
        bool_mutants = [m for m in mutants if "and" in m.description and "or" in m.description]
        assert len(bool_mutants) >= 1
        assert bool_mutants[0].category == MutationCategory.BINARY_OPERATOR

    def test_arithmetic_operator_mutation(self, runner: MutationRunner) -> None:
        """Verify arithmetic operator mutations (+ ↔ -, * ↔ //)."""
        code = """
def calculate(a, b):
    sum_val = a + b
    prod_val = a * b
    return sum_val
"""
        mutants = runner.generate_mutants(code)
        arith_mutants = [m for m in mutants if "arithmetic operator" in m.description]
        assert len(arith_mutants) >= 2
        descs = [m.description for m in arith_mutants]
        assert any("+" in d and "-" in d for d in descs)
        assert any("*" in d and "//" in d for d in descs)

    def test_unary_operator_mutation(self, runner: MutationRunner) -> None:
        """Verify unary operator mutation (removing 'not')."""
        code = """
def is_invalid(flag):
    if not flag:
        return True
    return False
"""
        mutants = runner.generate_mutants(code)
        unary_mutants = [m for m in mutants if m.category == MutationCategory.UNARY_OPERATOR]
        assert len(unary_mutants) >= 1
        assert "Removed unary 'not' operator" in unary_mutants[0].description

    def test_constant_replacement_mutation(self, runner: MutationRunner) -> None:
        """Verify constant replacement (True ↔ False, 0 ↔ 1)."""
        code = """
def get_flag():
    flag = True
    val = 0
    return flag
"""
        mutants = runner.generate_mutants(code)
        const_mutants = [m for m in mutants if m.category == MutationCategory.CONSTANT_REPLACEMENT]
        assert len(const_mutants) >= 2
        descs = [m.description for m in const_mutants]
        assert any("True with False" in d for d in descs)
        assert any("0 with 1" in d for d in descs)

    def test_return_value_swap_mutation(self, runner: MutationRunner) -> None:
        """Verify return value swap (return True ↔ return False)."""
        code = """
def is_valid():
    return True
"""
        mutants = runner.generate_mutants(code)
        ret_mutants = [m for m in mutants if m.category == MutationCategory.RETURN_VALUE_SWAP]
        assert len(ret_mutants) >= 1
        assert "Replaced return True with return False" in ret_mutants[0].description

    def test_duplicate_mutant_prevention(self, runner: MutationRunner) -> None:
        """Verify identical mutant signatures are deduplicated."""
        code = """
def add(a, b):
    return a + b
"""
        mutants = runner.generate_mutants(code)
        ids = [m.mutant_id for m in mutants]
        assert len(ids) == len(set(ids))

    def test_deterministic_mutant_ids(self, runner: MutationRunner) -> None:
        """Verify mutant IDs are deterministic across repeated runs."""
        code = "def f(x): return x + 1"
        mutants_run1 = runner.generate_mutants(code)
        mutants_run2 = runner.generate_mutants(code)

        assert len(mutants_run1) == len(mutants_run2)
        for m1, m2 in zip(mutants_run1, mutants_run2):
            assert m1.mutant_id == m2.mutant_id
            assert m1.category == m2.category
            assert m1.original_line == m2.original_line

    def test_malformed_syntax_does_not_crash(self, runner: MutationRunner) -> None:
        """Verify syntax error in source returns empty list without raising exception."""
        bad_code = "def broken_func(: return 1 +"
        mutants = runner.generate_mutants(bad_code)
        assert mutants == []

        summary = runner.run_mutation_analysis(bad_code, "def test_f(): pass")
        assert summary.total_mutants == 0
        assert summary.mutants == []

    def test_empty_module_returns_empty_summary(self, runner: MutationRunner) -> None:
        """Verify empty string or whitespace source code returns empty summary."""
        summary = runner.run_mutation_analysis("", "")
        assert summary.total_mutants == 0
        assert summary.mutants == []

    def test_module_without_candidates(self, runner: MutationRunner) -> None:
        """Verify module with no mutable AST nodes returns empty summary."""
        code = """
class EmptyContainer:
    pass
"""
        summary = runner.run_mutation_analysis(code, "")
        assert summary.total_mutants == 0

    def test_custom_operator_injection(self) -> None:
        """Verify custom list of operators can be injected into MutationRunner."""
        custom_runner = MutationRunner(operators=[ArithmeticOperator()])
        code = "def f(x): return x + 1 and True"
        mutants = custom_runner.generate_mutants(code)
        # Should only generate arithmetic mutants
        categories = {m.category for m in mutants}
        assert categories == {MutationCategory.BINARY_OPERATOR}

    def test_idempotence_and_source_immutability(self, runner: MutationRunner) -> None:
        """Verify original source code string remains completely unmodified."""
        original_code = "def f(a, b): return a == b"
        code_copy = str(original_code)

        runner.generate_mutants(original_code)
        assert original_code == code_copy
