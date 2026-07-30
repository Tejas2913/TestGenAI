"""TestGen AI v2.3 — Planner Output Validator & TestPlan Mapper

Parses, validates, and maps raw LLM provider responses into validated JSON objects
and domain TestPlan instances.
"""

import json
import re
from typing import Any, Dict, List
import structlog

from app.domain.v23_models import TestPlan
from app.exceptions.v23_exceptions import ValidationError

logger = structlog.get_logger()

REQUIRED_PLANNER_KEYS = {"target_functions", "test_cases", "required_mocks", "edge_cases"}


def strip_markdown_fences(text: str) -> str:
    """Clean markdown code block fences (e.g. ```json ... ```) from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        # Remove closing fence
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def validate_planner_json(raw_text: str) -> Dict[str, Any]:
    """Parse raw LLM response text into validated JSON dictionary.

    Args:
        raw_text: Text string returned by LLM provider.

    Returns:
        Validated dictionary payload.

    Raises:
        ValidationError: If JSON is malformed or required keys are missing.
    """
    cleaned_text = strip_markdown_fences(raw_text)

    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("planner_output", f"Malformed JSON output: {exc.msg} at line {exc.lineno} col {exc.colno}") from exc

    if not isinstance(data, dict):
        raise ValidationError("planner_output", f"Expected JSON object, got {type(data).__name__}")

    missing_keys = REQUIRED_PLANNER_KEYS - set(data.keys())
    if missing_keys:
        raise ValidationError("planner_output", f"JSON missing required planner keys: {sorted(list(missing_keys))}")

    if not isinstance(data.get("target_functions"), list):
        raise ValidationError("planner_output", "'target_functions' must be a list")

    if not isinstance(data.get("test_cases"), list):
        raise ValidationError("planner_output", "'test_cases' must be a list")

    return data


def map_json_to_test_plan(data: Dict[str, Any]) -> TestPlan:
    """Map validated planner JSON object into TestPlan domain model.

    Args:
        data: Validated JSON dictionary.

    Returns:
        Populated TestPlan object.
    """
    return TestPlan(
        target_functions=data.get("target_functions", []),
        test_cases=data.get("test_cases", []),
        mock_requirements=data.get("required_mocks", []),
        edge_cases=data.get("edge_cases", []),
    )
