"""TestGen AI v2.3 — Repair Output Validator & RepairedTest Mapper

Parses, validates, and maps raw LLM provider responses into validated JSON objects,
updated GeneratedTest instances, and RepairAction history entries.
"""

import json
from typing import Any, Dict, List, Tuple
import structlog

from app.domain.planner_schema import strip_markdown_fences
from app.domain.v23_models import GeneratedTest, RepairAction
from app.exceptions.v23_exceptions import ValidationError

logger = structlog.get_logger()

REQUIRED_REPAIR_KEYS = {"test_name", "test_code", "repair_reason"}


def validate_repair_json(raw_text: str) -> Dict[str, Any]:
    """Parse raw LLM response text into validated repair JSON dictionary.

    Args:
        raw_text: Text string returned by LLM provider.

    Returns:
        Validated dictionary payload.

    Raises:
        ValidationError: If JSON is malformed, missing required keys, or contains invalid test schemas.
    """
    cleaned_text = strip_markdown_fences(raw_text)

    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("repair_output", f"Malformed JSON output: {exc.msg} at line {exc.lineno} col {exc.colno}") from exc

    if not isinstance(data, dict):
        raise ValidationError("repair_output", f"Expected JSON object, got {type(data).__name__}")

    if "repaired_tests" not in data:
        raise ValidationError("repair_output", "JSON missing required root key 'repaired_tests'")

    tests = data["repaired_tests"]
    if not isinstance(tests, list):
        raise ValidationError("repair_output", "'repaired_tests' must be a list")

    if not tests:
        raise ValidationError("repair_output", "'repaired_tests' list must not be empty")

    seen_names = set()
    for idx, test in enumerate(tests):
        if not isinstance(test, dict):
            raise ValidationError("repair_output", f"Repaired test entry at index {idx} must be a JSON object")

        missing = REQUIRED_REPAIR_KEYS - set(test.keys())
        if missing:
            raise ValidationError("repair_output", f"Repaired test '{test.get('test_name', idx)}' missing required keys: {sorted(list(missing))}")

        test_name = test["test_name"]
        if not isinstance(test_name, str) or not test_name.strip():
            raise ValidationError("repair_output", f"Repaired test entry at index {idx} has invalid or empty 'test_name'")

        if test_name in seen_names:
            raise ValidationError("repair_output", f"Duplicate repaired test name detected: '{test_name}'")
        seen_names.add(test_name)

        test_code = test["test_code"]
        if not isinstance(test_code, str) or not test_code.strip():
            raise ValidationError("repair_output", f"Repaired test '{test_name}' has empty 'test_code'")

        confidence = test.get("confidence", 1.0)
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            raise ValidationError("repair_output", f"Repaired test '{test_name}' has invalid confidence: {confidence}")

    return data


def map_json_to_repaired_tests(
    data: Dict[str, Any],
    existing_tests: List[GeneratedTest],
) -> Tuple[List[GeneratedTest], List[RepairAction]]:
    """Map validated repair JSON dictionary into updated GeneratedTest objects and RepairAction history.

    Args:
        data: Validated repair dictionary.
        existing_tests: Original list of GeneratedTest instances.

    Returns:
        Tuple of (updated GeneratedTest list, RepairAction list).
    """
    repaired_entries = data.get("repaired_tests", [])
    repaired_dict = {entry["test_name"]: entry for entry in repaired_entries}

    updated_tests: List[GeneratedTest] = []
    repair_actions: List[RepairAction] = []

    # Map onto existing tests or add new repaired tests
    existing_names = set()
    for original in existing_tests:
        existing_names.add(original.test_name)
        if original.test_name in repaired_dict:
            rep = repaired_dict[original.test_name]
            new_code = rep["test_code"]
            reason = rep.get("repair_reason", "Surgical repair applied")
            
            # Create updated GeneratedTest
            updated_gt = GeneratedTest(
                test_name=original.test_name,
                test_code=new_code,
                target_function=rep.get("target_function") or original.target_function,
                target_module=original.target_module,
                framework=original.framework,
                imports=original.imports,
                fixtures=original.fixtures,
                mocks=original.mocks,
                setup=original.setup,
                assertions=original.assertions,
                confidence=float(rep.get("confidence", original.confidence)),
            )
            updated_tests.append(updated_gt)

            # Create RepairAction entry
            action = RepairAction(
                repair_type="AIRefinementRepair",
                original_code=original.test_code,
                repaired_code=new_code,
                reason=reason,
            )
            repair_actions.append(action)
        else:
            updated_tests.append(original)

    # Process any new repaired tests not matching an existing name
    for name, rep in repaired_dict.items():
        if name not in existing_names:
            new_code = rep["test_code"]
            reason = rep.get("repair_reason", "New test added during repair")
            updated_gt = GeneratedTest(
                test_name=name,
                test_code=new_code,
                target_function=rep.get("target_function", "unknown"),
                confidence=float(rep.get("confidence", 1.0)),
            )
            updated_tests.append(updated_gt)

            action = RepairAction(
                repair_type="AIRefinementRepair",
                original_code="",
                repaired_code=new_code,
                reason=reason,
            )
            repair_actions.append(action)

    return updated_tests, repair_actions
