"""Tests for the ResponseParser module."""

import pytest

from app.ai.response_parser import ResponseParser
from app.exceptions import ValidationException

SAMPLE_JSON = '''{
  "function_name": "add",
  "test_cases": [
    {
      "name": "test_add_positive_numbers",
      "description": "Test adding two positive integers",
      "category": "happy_path",
      "inputs": {"a": 1, "b": 2},
      "expected_output": 3,
      "assertions": ["assert add(1, 2) == 3"]
    },
    {
      "name": "test_add_zeros",
      "description": "Test adding zeros",
      "category": "edge_case",
      "inputs": {"a": 0, "b": 0},
      "expected_output": 0,
      "assertions": ["assert add(0, 0) == 0"]
    },
    {
      "name": "test_add_negative_numbers",
      "description": "Test adding negative numbers",
      "category": "boundary",
      "inputs": {"a": -1, "b": -2},
      "expected_output": -3,
      "assertions": ["assert add(-1, -2) == -3"]
    }
  ],
  "imports": ["from mymodule import add"],
  "setup_code": null
}'''


class TestResponseParserCleanJSON:
    """Tests for parsing clean, well-formed JSON."""

    def test_parse_clean_json(self):
        """Parse raw JSON directly."""
        parser = ResponseParser()
        result = parser.parse(SAMPLE_JSON)

        assert result.function_name == "add"
        assert len(result.test_cases) == 3
        assert result.test_cases[0].name == "test_add_positive_numbers"
        assert result.test_cases[0].category == "happy_path"
        assert result.imports == ["from mymodule import add"]

    def test_parse_returns_typed_test_cases(self):
        """Test cases are strongly typed TestCase objects, not dicts."""
        parser = ResponseParser()
        result = parser.parse(SAMPLE_JSON)

        tc = result.test_cases[0]
        assert tc.inputs == {"a": 1, "b": 2}
        assert tc.expected_output == 3
        assert tc.assertions == ["assert add(1, 2) == 3"]


class TestResponseParserFencedJSON:
    """Tests for extracting JSON from markdown code fences."""

    def test_parse_fenced_json(self):
        """Extract JSON from ```json ... ``` fences."""
        raw = f"Here are the tests:\n```json\n{SAMPLE_JSON}\n```\nDone!"
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.function_name == "add"
        assert len(result.test_cases) == 3

    def test_parse_fenced_without_language_tag(self):
        """Extract JSON from ``` ... ``` fences without language tag."""
        raw = f"```\n{SAMPLE_JSON}\n```"
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.function_name == "add"

    def test_parse_json_with_surrounding_text(self):
        """Extract JSON when surrounded by explanation text."""
        raw = f"I generated these tests for you:\n{SAMPLE_JSON}\nLet me know if you need more."
        parser = ResponseParser()
        result = parser.parse(raw)

        assert result.function_name == "add"


class TestResponseParserErrors:
    """Tests for error handling."""

    def test_parse_invalid_json_raises(self):
        """Raise ValidationException for malformed JSON."""
        with pytest.raises(ValidationException, match="Failed to parse"):
            ResponseParser().parse("not json at all {{{")

    def test_parse_json_array_raises(self):
        """Raise ValidationException when JSON is an array."""
        with pytest.raises(ValidationException, match="must be an object"):
            ResponseParser().parse("[1, 2, 3]")
