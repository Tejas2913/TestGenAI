"""Tests for the PromptBuilder module."""

from app.ai.prompt_builder import PromptBuilder
from app.domain.code_metadata import CodeMetadata
from app.domain.parameter import ParameterInfo


def _make_metadata() -> CodeMetadata:
    """Create sample CodeMetadata for tests."""
    return CodeMetadata(
        function_name="calculate_discount",
        parameters=[
            ParameterInfo(name="price", type_hint="float"),
            ParameterInfo(name="discount_percent", type_hint="float", default_value="0.0"),
        ],
        return_type="float",
        docstring="Apply a discount to a price.",
        class_name=None,
        decorators=[],
        source_code='def calculate_discount(price: float, discount_percent: float = 0.0) -> float:\n    """Apply a discount to a price."""\n    return price * (1 - discount_percent / 100)',
    )


class TestPromptBuilder:
    """Tests for PromptBuilder template loading and variable injection."""

    def test_build_returns_prompt_payload(self):
        """PromptBuilder returns a PromptPayload with all three prompts."""
        builder = PromptBuilder()
        result = builder.build(_make_metadata())

        assert result.system_prompt
        assert result.developer_prompt
        assert result.user_prompt

    def test_developer_prompt_contains_function_name(self):
        """Developer prompt includes the function name from metadata."""
        builder = PromptBuilder()
        result = builder.build(_make_metadata())

        assert "calculate_discount" in result.developer_prompt

    def test_developer_prompt_contains_parameters(self):
        """Developer prompt includes parameter info."""
        builder = PromptBuilder()
        result = builder.build(_make_metadata())

        assert "price" in result.developer_prompt
        assert "discount_percent" in result.developer_prompt

    def test_user_prompt_contains_source_code(self):
        """User prompt includes the original source code."""
        builder = PromptBuilder()
        result = builder.build(_make_metadata())

        assert "def calculate_discount" in result.user_prompt

    def test_user_prompt_includes_specification(self):
        """User prompt includes the specification when provided."""
        builder = PromptBuilder()
        result = builder.build(
            _make_metadata(),
            specification="Should handle negative prices by raising ValueError",
        )

        assert "negative prices" in result.user_prompt

    def test_user_prompt_without_specification(self):
        """User prompt works without a specification."""
        builder = PromptBuilder()
        result = builder.build(_make_metadata(), specification=None)

        assert "Specification:" not in result.user_prompt
