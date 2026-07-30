"""TestGen AI v2.3 — Generator Output Validator & GeneratedTest Mapper

Parses, validates, and maps raw LLM provider responses into validated JSON objects
and strongly typed GeneratedTest domain model instances.
"""

import json
from typing import Any, Dict, List
import structlog

from app.domain.planner_schema import strip_markdown_fences
from app.domain.v23_models import GeneratedTest
from app.exceptions.v23_exceptions import ValidationError

logger = structlog.get_logger()

REQUIRED_TEST_KEYS = {"test_name", "test_code", "target_function"}


def validate_generator_json(raw_text: str) -> Dict[str, Any]:
    """Parse raw LLM response text into validated generator JSON payload.

    Args:
        raw_text: Text string returned by LLM provider.

    Returns:
        Validated dictionary payload containing 'generated_tests'.

    Raises:
        ValidationError: If JSON is malformed, missing required keys, contains duplicate test names, or empty test code.
    """
    cleaned_text = strip_markdown_fences(raw_text)

    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("generator_output", f"Malformed JSON output: {exc.msg} at line {exc.lineno} col {exc.colno}") from exc

    if not isinstance(data, dict):
        raise ValidationError("generator_output", f"Expected JSON object, got {type(data).__name__}")

    if "generated_tests" not in data:
        raise ValidationError("generator_output", "JSON missing required root key 'generated_tests'")

    tests = data["generated_tests"]
    if not isinstance(tests, list):
        raise ValidationError("generator_output", "'generated_tests' must be a list")

    if not tests:
        raise ValidationError("generator_output", "'generated_tests' list must not be empty")

    seen_names = set()
    for idx, test in enumerate(tests):
        if not isinstance(test, dict):
            raise ValidationError("generator_output", f"Test entry at index {idx} must be a JSON object")

        missing = REQUIRED_TEST_KEYS - set(test.keys())
        if missing:
            raise ValidationError("generator_output", f"Test entry '{test.get('test_name', idx)}' missing required keys: {sorted(list(missing))}")

        test_name = test["test_name"]
        if not isinstance(test_name, str) or not test_name.strip():
            raise ValidationError("generator_output", f"Test entry at index {idx} has invalid or empty 'test_name'")

        if test_name in seen_names:
            raise ValidationError("generator_output", f"Duplicate test name detected: '{test_name}'")
        seen_names.add(test_name)

        test_code = test["test_code"]
        if not isinstance(test_code, str) or not test_code.strip():
            raise ValidationError("generator_output", f"Test '{test_name}' has empty 'test_code'")

        confidence = test.get("confidence", 1.0)
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            raise ValidationError("generator_output", f"Test '{test_name}' has invalid confidence: {confidence}")

    return data


def map_json_to_generated_tests(data: Dict[str, Any]) -> List[GeneratedTest]:
    """Map validated generator JSON dictionary into a list of GeneratedTest domain objects.

    Args:
        data: Validated generator dictionary.

    Returns:
        List of populated GeneratedTest instances.
    """
    results: List[GeneratedTest] = []
    for entry in data.get("generated_tests", []):
        test_obj = GeneratedTest(
            test_name=entry.get("test_name", ""),
            test_code=entry.get("test_code", ""),
            target_function=entry.get("target_function", ""),
            target_module=entry.get("target_module", ""),
            framework=entry.get("framework", "pytest"),
            imports=entry.get("imports", []),
            fixtures=entry.get("fixtures", []),
            mocks=entry.get("mocks", []),
            setup=entry.get("setup", ""),
            assertions=entry.get("assertions", []),
            confidence=float(entry.get("confidence", 1.0)),
        )
        results.append(test_obj)
    return results
