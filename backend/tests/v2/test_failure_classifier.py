"""Unit tests for Phase 1 failure classification.

Tests that FailureCategory and classify_sandbox_failure:
  - classify TypeError, ModuleNotFoundError, ImportError, NameError, SyntaxError, IndentationError as repairable
  - classify AssertionError, TimeoutExpired, SANDBOX_UNAVAILABLE, security errors as non-repairable
  - return concise, structured human-readable reasons
  - default to UNKNOWN non-repairable for unclassified or empty stderr
"""

import pytest

from app.domain.failure_classifier import (
    FailureCategory,
    FailureClassification,
    classify_sandbox_failure,
)


class TestFailureClassifier:
    """Structured Failure Classifier unit tests."""

    def test_success_exit_code_returns_non_repairable(self) -> None:
        res = classify_sandbox_failure(exit_code=0, stdout="passed")
        assert res.category == FailureCategory.UNKNOWN
        assert res.is_repairable is False

    def test_type_error_missing_argument(self) -> None:
        stderr = "TypeError: calculate_discount() missing 2 required positional arguments: 'price' and 'discount_percent'"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.TYPE_ERROR
        assert res.is_repairable is True
        assert res.reason == "Missing required positional argument"

    def test_type_error_unexpected_keyword(self) -> None:
        stderr = "TypeError: calculate_discount() got an unexpected keyword argument 'foo'"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.TYPE_ERROR
        assert res.is_repairable is True
        assert res.reason == "Unexpected keyword argument"

    def test_module_not_found(self) -> None:
        stderr = "ModuleNotFoundError: No module named 'utils'"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.MODULE_NOT_FOUND
        assert res.is_repairable is True
        assert res.reason == "Module import failed"

    def test_import_error(self) -> None:
        stderr = "ImportError: cannot import name 'calculate' from 'main'"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.IMPORT_ERROR
        assert res.is_repairable is True

    def test_syntax_error(self) -> None:
        stderr = "SyntaxError: invalid syntax on line 12"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.SYNTAX_ERROR
        assert res.is_repairable is True

    def test_indentation_error(self) -> None:
        stderr = "IndentationError: unexpected indent"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.INDENTATION_ERROR
        assert res.is_repairable is True

    def test_assertion_error_non_repairable(self) -> None:
        stderr = "AssertionError: assert 100.0 == 75.0"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.ASSERTION_ERROR
        assert res.is_repairable is False

    def test_timeout_non_repairable(self) -> None:
        stderr = "TimeoutExpired: command exceeded 5s timeout"
        res = classify_sandbox_failure(exit_code=1, stderr=stderr)
        assert res.category == FailureCategory.TIMEOUT
        assert res.is_repairable is False

    def test_sandbox_unavailable_non_repairable(self) -> None:
        stderr = "SANDBOX_UNAVAILABLE: Connection refused"
        res = classify_sandbox_failure(exit_code=-1, stderr=stderr)
        assert res.category == FailureCategory.SANDBOX_UNAVAILABLE
        assert res.is_repairable is False

    def test_empty_output_returns_unknown(self) -> None:
        res = classify_sandbox_failure(exit_code=1, stderr="", stdout="")
        assert res.category == FailureCategory.UNKNOWN
        assert res.is_repairable is False
