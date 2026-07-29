"""Unit tests for Phase 2 repair prompt construction.

Tests that PromptBuilder.build_repair_prompt:
  - loads app/prompts/v1/repair.txt template
  - injects source_code, generated_tests, traceback, failure_category, rule_id, and failure_reason
  - returns a valid PromptPayload with system_prompt and developer_prompt
"""

import pytest

from app.ai.prompt_builder import PromptBuilder
from app.domain.failure_classifier import FailureCategory


class TestRepairPromptBuilder:
    """Repair prompt loading and variable injection tests."""

    def test_build_repair_prompt_injects_all_placeholders(self) -> None:
        builder = PromptBuilder(prompt_version="v1")

        payload = builder.build_repair_prompt(
            source_code="def calculate_discount(price, percent):\n    return price * (1 - percent/100)",
            generated_tests="def test_calc():\n    assert calculate_discount() == 75.0",
            traceback="TypeError: calculate_discount() missing 2 required positional arguments: 'price' and 'percent'",
            failure_category=FailureCategory.TYPE_ERROR,
            rule_id="TYPE_ERROR_MISSING_ARGUMENT",
            failure_reason="Missing required positional argument",
        )

        assert payload.system_prompt == "You are an expert Python automated test repair engine."
        assert "TYPE_ERROR" in payload.developer_prompt
        assert "TYPE_ERROR_MISSING_ARGUMENT" in payload.developer_prompt
        assert "Missing required positional argument" in payload.developer_prompt
        assert "def calculate_discount(price, percent):" in payload.developer_prompt
        assert "TypeError: calculate_discount() missing 2 required positional arguments" in payload.developer_prompt

    def test_build_repair_prompt_does_not_alter_standard_build(self) -> None:
        builder = PromptBuilder(prompt_version="v1")
        from app.domain.code_metadata import CodeMetadata

        meta = CodeMetadata(
            function_name="calculate_discount",
            parameters=[],
            source_code="def calculate_discount(): pass",
        )

        standard_payload = builder.build(meta)
        assert standard_payload.system_prompt is not None
        assert "You are a test specification engine." in standard_payload.system_prompt
