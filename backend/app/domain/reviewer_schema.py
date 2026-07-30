"""TestGen AI v2.3 — Reviewer Output Validator & ReviewReport Mapper

Parses, validates, and maps raw LLM provider responses into validated JSON objects
and strongly typed ReviewReport domain model instances.
"""

import json
from typing import Any, Dict, List
import structlog

from app.domain.planner_schema import strip_markdown_fences
from app.domain.v23_models import ReviewReport
from app.exceptions.v23_exceptions import ValidationError

logger = structlog.get_logger()

REQUIRED_REVIEW_KEYS = {"overall_score", "approved", "summary", "issues"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def validate_review_json(raw_text: str) -> Dict[str, Any]:
    """Parse raw LLM response text into validated reviewer JSON dictionary.

    Args:
        raw_text: Text string returned by LLM provider.

    Returns:
        Validated dictionary payload.

    Raises:
        ValidationError: If JSON is malformed, missing required keys, contains out-of-range scores, or invalid issue schemas.
    """
    cleaned_text = strip_markdown_fences(raw_text)

    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("reviewer_output", f"Malformed JSON output: {exc.msg} at line {exc.lineno} col {exc.colno}") from exc

    if not isinstance(data, dict):
        raise ValidationError("reviewer_output", f"Expected JSON object, got {type(data).__name__}")

    missing_keys = REQUIRED_REVIEW_KEYS - set(data.keys())
    if missing_keys:
        raise ValidationError("reviewer_output", f"JSON missing required reviewer keys: {sorted(list(missing_keys))}")

    overall_score = data["overall_score"]
    if not isinstance(overall_score, (int, float)) or not (0 <= overall_score <= 100):
        raise ValidationError("reviewer_output", f"'overall_score' must be a number between 0 and 100, got: {overall_score}")

    approved = data["approved"]
    if not isinstance(approved, bool):
        raise ValidationError("reviewer_output", f"'approved' must be a boolean, got {type(approved).__name__}")

    confidence = data.get("confidence", 1.0)
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise ValidationError("reviewer_output", f"'confidence' must be between 0.0 and 1.0, got: {confidence}")

    issues = data["issues"]
    if not isinstance(issues, list):
        raise ValidationError("reviewer_output", "'issues' must be a list")

    seen_issues = set()
    for idx, issue in enumerate(issues):
        if not isinstance(issue, dict):
            raise ValidationError("reviewer_output", f"Issue entry at index {idx} must be a JSON object")

        severity = issue.get("severity", "medium").lower()
        if severity not in VALID_SEVERITIES:
            raise ValidationError("reviewer_output", f"Issue at index {idx} has invalid severity '{severity}'. Must be one of {sorted(list(VALID_SEVERITIES))}")

        category = issue.get("category", "general")
        desc = issue.get("description", "")
        if not isinstance(desc, str) or not desc.strip():
            raise ValidationError("reviewer_output", f"Issue at index {idx} has empty or invalid 'description'")

        issue_signature = f"{category}:{desc.strip()}"
        if issue_signature in seen_issues:
            raise ValidationError("reviewer_output", f"Duplicate issue detected: '{desc}'")
        seen_issues.add(issue_signature)

    return data


def map_json_to_review_report(data: Dict[str, Any]) -> ReviewReport:
    """Map validated reviewer JSON dictionary into ReviewReport domain model.

    Args:
        data: Validated reviewer dictionary.

    Returns:
        Populated ReviewReport object.
    """
    is_approved = bool(data.get("approved", True))
    overall_score = float(data.get("overall_score", 100.0))
    summary = str(data.get("summary", ""))
    coverage_analysis = str(data.get("coverage_analysis", ""))
    issues = data.get("issues", [])
    strengths = data.get("strengths", [])
    recommendations = data.get("recommendations", [])
    confidence = float(data.get("confidence", 1.0))

    # Derive flaws and missing_assertions for backward compatibility
    flaws = [f"{iss.get('category', 'issue')}: {iss.get('description', '')}" for iss in issues]
    missing_assertions = [iss.get("description", "") for iss in issues if iss.get("category") == "assertion"]
    smell_diagnostics = issues

    return ReviewReport(
        is_approved=is_approved,
        overall_score=overall_score,
        summary=summary,
        coverage_analysis=coverage_analysis,
        issues=issues,
        strengths=strengths,
        recommendations=recommendations,
        confidence=confidence,
        flaws=flaws,
        missing_assertions=missing_assertions,
        smell_diagnostics=smell_diagnostics,
    )
