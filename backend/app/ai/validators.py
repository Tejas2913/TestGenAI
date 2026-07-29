"""Validation layer for generated test suites.

Three validators with distinct responsibilities:
- JSONSchemaValidator: structural correctness
- SemanticValidator: content quality
- BusinessRuleValidator: project conventions and requirements
"""

from app.domain.test_case import ALLOWED_CATEGORIES, TestCase
from app.domain.test_suite import TestSuite
from app.exceptions import ValidationException


class JSONSchemaValidator:
    """Validates structural correctness of a TestSuite.

    Checks that required fields are present, types are correct,
    and categories belong to the allowed set.
    """

    def validate(self, test_suite: TestSuite) -> list[str]:
        """Return a list of validation warnings. Raise on critical errors."""
        warnings: list[str] = []

        if not test_suite.function_name:
            raise ValidationException(detail="TestSuite is missing function_name")

        if not test_suite.test_cases:
            raise ValidationException(detail="TestSuite contains no test cases")

        for index, tc in enumerate(test_suite.test_cases):
            warnings.extend(self._validate_test_case(tc, index))

        return warnings

    def _validate_test_case(self, tc: TestCase, index: int) -> list[str]:
        """Validate a single test case's structural integrity."""
        warnings: list[str] = []
        label = f"test_cases[{index}] ({tc.name})"

        if not tc.name:
            raise ValidationException(detail=f"{label}: missing 'name'")

        if not tc.description:
            warnings.append(f"{label}: empty description")

        if tc.category not in ALLOWED_CATEGORIES:
            warnings.append(
                f"{label}: unknown category '{tc.category}', "
                f"expected one of {sorted(ALLOWED_CATEGORIES)}"
            )

        if not tc.assertions:
            warnings.append(f"{label}: no assertions defined")

        return warnings


class SemanticValidator:
    """Validates content quality and meaningfulness of test cases."""

    def validate(self, test_suite: TestSuite) -> list[str]:
        """Return a list of semantic quality warnings."""
        warnings: list[str] = []

        for index, tc in enumerate(test_suite.test_cases):
            label = f"test_cases[{index}] ({tc.name})"

            if tc.expected_output is None or tc.expected_output == "":
                warnings.append(f"{label}: empty expected_output")

            for a_index, assertion in enumerate(tc.assertions):
                if not assertion.strip().startswith("assert"):
                    warnings.append(
                        f"{label}: assertions[{a_index}] does not start with 'assert'"
                    )

        return warnings


class BusinessRuleValidator:
    """Validates project-level conventions and test coverage requirements."""

    REQUIRED_CATEGORIES = {"happy_path", "edge_case", "error_handling"}

    def validate(self, test_suite: TestSuite) -> list[str]:
        """Return a list of business rule warnings."""
        warnings: list[str] = []

        warnings.extend(self._check_duplicate_names(test_suite))
        warnings.extend(self._check_naming_convention(test_suite))
        warnings.extend(self._check_required_categories(test_suite))

        return warnings

    def _check_duplicate_names(self, test_suite: TestSuite) -> list[str]:
        """Detect test cases with identical names."""
        seen: set[str] = set()
        warnings: list[str] = []
        for tc in test_suite.test_cases:
            if tc.name in seen:
                warnings.append(f"Duplicate test name: '{tc.name}'")
            seen.add(tc.name)
        return warnings

    def _check_naming_convention(self, test_suite: TestSuite) -> list[str]:
        """Ensure all test names follow the test_ prefix convention."""
        warnings: list[str] = []
        for tc in test_suite.test_cases:
            if not tc.name.startswith("test_"):
                warnings.append(
                    f"Test '{tc.name}' does not follow 'test_' naming convention"
                )
        return warnings

    def _check_required_categories(self, test_suite: TestSuite) -> list[str]:
        """Verify that at least one test exists for each required category."""
        present = {tc.category for tc in test_suite.test_cases}
        missing = self.REQUIRED_CATEGORIES - present
        warnings: list[str] = []
        if missing:
            warnings.append(
                f"Missing required test categories: {sorted(missing)}"
            )
        return warnings


class TestCodeValidator:
    """Validates raw executable Python test source code.

    Used as the single unified validation entry point for Python test code.
    Strips markdown code fences, verifies AST syntax, and ensures non-empty code.
    """

    def validate_code(self, raw_code: str) -> str:
        """Strip markdown fences and validate Python syntax via AST parsing.

        Returns:
            Clean executable Python test code string.

        Raises:
            ValidationException: If syntax is invalid or code is empty.
        """
        code = self._strip_markdown(raw_code)
        if not code.strip():
            raise ValidationException(detail="Test code is empty")

        import ast
        try:
            ast.parse(code)
        except SyntaxError as exc:
            raise ValidationException(
                detail=f"Test code syntax validation failed: {exc.msg}"
            ) from exc

        return code

    @staticmethod
    def _strip_markdown(raw: str) -> str:
        """Remove ```python ... ``` fences from raw LLM output."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()
