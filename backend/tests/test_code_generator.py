"""Tests for the CodeGenerator module."""

from app.ai.code_generator import CodeGenerator
from app.domain.test_case import TestCase
from app.domain.test_suite import TestSuite


def _make_test_suite() -> TestSuite:
    """Create a sample TestSuite for code generation tests."""
    return TestSuite(
        function_name="add",
        test_cases=[
            TestCase(
                name="test_add_positive_numbers",
                description="Test adding two positive integers",
                category="happy_path",
                inputs={"a": 1, "b": 2},
                expected_output=3,
                assertions=["assert add(1, 2) == 3"],
            ),
            TestCase(
                name="test_add_zeros",
                description="Test adding zeros",
                category="edge_case",
                inputs={"a": 0, "b": 0},
                expected_output=0,
                assertions=["assert add(0, 0) == 0"],
            ),
            TestCase(
                name="test_add_negative",
                description="Test adding negative numbers",
                category="error_handling",
                inputs={"a": -1, "b": -2},
                expected_output=-3,
                assertions=[
                    "result = add(-1, -2)",
                    "assert result == -3",
                ],
            ),
        ],
        imports=["from mymodule import add"],
        setup_code=None,
    )


class TestCodeGenerator:
    """Tests for pytest code generation."""

    def test_generate_produces_string(self):
        """CodeGenerator returns a non-empty string."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert isinstance(code, str)
        assert len(code) > 0

    def test_generated_code_has_imports(self):
        """Generated code includes import statements."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert "import pytest" in code
        assert "from mymodule import add" in code

    def test_generated_code_has_all_test_functions(self):
        """Generated code includes all test function definitions."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert "def test_add_positive_numbers():" in code
        assert "def test_add_zeros():" in code
        assert "def test_add_negative():" in code

    def test_generated_code_has_docstrings(self):
        """Generated code includes test docstrings."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert "Test adding two positive integers" in code

    def test_generated_code_has_assertions(self):
        """Generated code includes assertion statements."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert "assert add(1, 2) == 3" in code
        assert "assert add(0, 0) == 0" in code
        assert "assert result == -3" in code

    def test_generated_code_includes_category_in_docstring(self):
        """Generated code annotates each test with its category."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert "Category: happy_path" in code
        assert "Category: edge_case" in code

    def test_generated_code_has_module_docstring(self):
        """Generated code has a top-level module docstring."""
        generator = CodeGenerator()
        code = generator.generate(_make_test_suite())

        assert '"""Auto-generated tests for add."""' in code

    def test_generate_with_setup_code(self):
        """Generated code includes setup_code when provided."""
        suite = _make_test_suite()
        suite.setup_code = "DATA = [1, 2, 3]"

        generator = CodeGenerator()
        code = generator.generate(suite)

        assert "DATA = [1, 2, 3]" in code
