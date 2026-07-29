"""Tests for the Validators module."""

import pytest

from app.ai.validators import (
    BusinessRuleValidator,
    JSONSchemaValidator,
    SemanticValidator,
)
from app.domain.test_case import TestCase
from app.domain.test_suite import TestSuite
from app.exceptions import ValidationException


def _make_test_suite(**overrides) -> TestSuite:
    """Create a valid baseline TestSuite for tests."""
    defaults = {
        "function_name": "add",
        "test_cases": [
            TestCase(
                name="test_add_positive",
                description="Add two positive numbers",
                category="happy_path",
                inputs={"a": 1, "b": 2},
                expected_output=3,
                assertions=["assert add(1, 2) == 3"],
            ),
            TestCase(
                name="test_add_zeros",
                description="Add zeros",
                category="edge_case",
                inputs={"a": 0, "b": 0},
                expected_output=0,
                assertions=["assert add(0, 0) == 0"],
            ),
            TestCase(
                name="test_add_type_error",
                description="Adding incompatible types raises TypeError",
                category="error_handling",
                inputs={"a": "1", "b": 2},
                expected_output="raises TypeError",
                assertions=["assert add('1', 2)"],
            ),
        ],
        "imports": ["from mymodule import add"],
    }
    defaults.update(overrides)
    return TestSuite(**defaults)


class TestJSONSchemaValidator:
    """Tests for structural validation."""

    def test_valid_suite_returns_no_warnings(self):
        """A well-formed suite passes with no warnings."""
        validator = JSONSchemaValidator()
        warnings = validator.validate(_make_test_suite())
        assert warnings == []

    def test_empty_test_cases_raises(self):
        """Raise when no test cases are present."""
        suite = _make_test_suite(test_cases=[])
        with pytest.raises(ValidationException, match="no test cases"):
            JSONSchemaValidator().validate(suite)

    def test_unknown_category_warns(self):
        """Warn when a test case uses an unrecognized category."""
        suite = _make_test_suite(
            test_cases=[
                TestCase(
                    name="test_weird",
                    description="desc",
                    category="unknown_cat",
                    inputs={},
                    expected_output=1,
                    assertions=["assert True"],
                )
            ]
        )
        warnings = JSONSchemaValidator().validate(suite)
        assert any("unknown category" in w for w in warnings)

    def test_empty_assertions_warns(self):
        """Warn when a test case has no assertions."""
        suite = _make_test_suite(
            test_cases=[
                TestCase(
                    name="test_no_asserts",
                    description="desc",
                    category="happy_path",
                    inputs={},
                    expected_output=1,
                    assertions=[],
                )
            ]
        )
        warnings = JSONSchemaValidator().validate(suite)
        assert any("no assertions" in w for w in warnings)


class TestSemanticValidator:
    """Tests for content quality checks."""

    def test_valid_suite_returns_no_warnings(self):
        """A well-formed suite passes semantic checks."""
        validator = SemanticValidator()
        warnings = validator.validate(_make_test_suite())
        assert warnings == []

    def test_empty_expected_output_warns(self):
        """Warn when expected_output is empty."""
        suite = _make_test_suite(
            test_cases=[
                TestCase(
                    name="test_empty",
                    description="desc",
                    category="happy_path",
                    inputs={},
                    expected_output="",
                    assertions=["assert True"],
                )
            ]
        )
        warnings = SemanticValidator().validate(suite)
        assert any("empty expected_output" in w for w in warnings)

    def test_non_assert_statement_warns(self):
        """Warn when an assertion doesn't start with 'assert'."""
        suite = _make_test_suite(
            test_cases=[
                TestCase(
                    name="test_bad_assert",
                    description="desc",
                    category="happy_path",
                    inputs={},
                    expected_output=1,
                    assertions=["result == 1"],
                )
            ]
        )
        warnings = SemanticValidator().validate(suite)
        assert any("does not start with 'assert'" in w for w in warnings)


class TestBusinessRuleValidator:
    """Tests for project convention checks."""

    def test_valid_suite_returns_no_warnings(self):
        """A suite with all required categories passes."""
        validator = BusinessRuleValidator()
        warnings = validator.validate(_make_test_suite())
        assert warnings == []

    def test_duplicate_names_warns(self):
        """Warn when two test cases share the same name."""
        tc = TestCase(
            name="test_dup",
            description="desc",
            category="happy_path",
            inputs={},
            expected_output=1,
            assertions=["assert True"],
        )
        suite = _make_test_suite(test_cases=[tc, tc])
        warnings = BusinessRuleValidator().validate(suite)
        assert any("Duplicate test name" in w for w in warnings)

    def test_missing_test_prefix_warns(self):
        """Warn when a test name doesn't start with test_."""
        suite = _make_test_suite(
            test_cases=[
                TestCase(
                    name="add_positive",
                    description="desc",
                    category="happy_path",
                    inputs={},
                    expected_output=1,
                    assertions=["assert True"],
                )
            ]
        )
        warnings = BusinessRuleValidator().validate(suite)
        assert any("naming convention" in w for w in warnings)

    def test_missing_required_categories_warns(self):
        """Warn when required categories are missing."""
        suite = _make_test_suite(
            test_cases=[
                TestCase(
                    name="test_only_happy",
                    description="desc",
                    category="happy_path",
                    inputs={},
                    expected_output=1,
                    assertions=["assert True"],
                )
            ]
        )
        warnings = BusinessRuleValidator().validate(suite)
        assert any("Missing required test categories" in w for w in warnings)
