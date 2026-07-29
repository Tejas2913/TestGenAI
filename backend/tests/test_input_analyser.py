"""Tests for the InputAnalyser module."""

import pytest

from app.ai.input_analyser import InputAnalyser
from app.exceptions import ValidationException


class TestInputAnalyserSimpleFunction:
    """Tests for analysing standalone functions."""

    def test_analyse_simple_function(self):
        """Extract metadata from a basic function."""
        source = '''
def add(a, b):
    """Add two numbers."""
    return a + b
'''
        analyser = InputAnalyser()
        result = analyser.analyse(source)

        assert result.function_name == "add"
        assert len(result.parameters) == 2
        assert result.parameters[0].name == "a"
        assert result.parameters[1].name == "b"
        assert result.docstring == "Add two numbers."
        assert result.class_name is None
        assert result.return_type is None

    def test_analyse_typed_function(self):
        """Extract type hints and return type."""
        source = '''
def multiply(x: int, y: int) -> int:
    """Multiply two integers."""
    return x * y
'''
        analyser = InputAnalyser()
        result = analyser.analyse(source)

        assert result.function_name == "multiply"
        assert result.parameters[0].type_hint == "int"
        assert result.parameters[1].type_hint == "int"
        assert result.return_type == "int"

    def test_analyse_function_with_defaults(self):
        """Extract default parameter values."""
        source = '''
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
'''
        analyser = InputAnalyser()
        result = analyser.analyse(source)

        assert result.parameters[0].default_value is None
        assert result.parameters[1].default_value == "'Hello'"


class TestInputAnalyserClassMethod:
    """Tests for analysing methods within classes."""

    def test_analyse_class_method(self):
        """Extract class context and skip self parameter."""
        source = '''
class Calculator:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
'''
        analyser = InputAnalyser()
        result = analyser.analyse(source)

        assert result.function_name == "add"
        assert result.class_name == "Calculator"
        assert len(result.parameters) == 2
        assert result.parameters[0].name == "a"

    def test_analyse_decorated_function(self):
        """Extract decorators."""
        source = '''
class Service:
    @staticmethod
    def process(data: list) -> list:
        return sorted(data)
'''
        analyser = InputAnalyser()
        result = analyser.analyse(source)

        assert "staticmethod" in result.decorators


class TestInputAnalyserErrors:
    """Tests for error handling."""

    def test_invalid_syntax_raises_exception(self):
        """Raise ValidationException on syntax errors."""
        with pytest.raises(ValidationException, match="Failed to parse"):
            InputAnalyser().analyse("def broken(")

    def test_no_function_raises_exception(self):
        """Raise ValidationException when no function is found."""
        with pytest.raises(ValidationException, match="No function definition"):
            InputAnalyser().analyse("x = 42")
