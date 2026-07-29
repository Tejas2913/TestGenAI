"""Structured Sandbox Failure Classifier.

Categorizes container stderr output into structured failure categories and
determines repairability for the Self-Healing pipeline.
"""

from dataclasses import dataclass
from enum import StrEnum
import re


class FailureCategory(StrEnum):
    """Structured categories for sandbox test execution failures."""

    TYPE_ERROR = "TYPE_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    MODULE_NOT_FOUND = "MODULE_NOT_FOUND"
    NAME_ERROR = "NAME_ERROR"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    INDENTATION_ERROR = "INDENTATION_ERROR"
    ATTRIBUTE_ERROR = "ATTRIBUTE_ERROR"
    ASSERTION_ERROR = "ASSERTION_ERROR"
    TIMEOUT = "TIMEOUT"
    SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"
    SECURITY_ERROR = "SECURITY_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FailureClassification:
    """Classification result for a failed sandbox execution.

    Fields:
        category      — Structured failure category enum
        rule_id       — Internal classifier rule identifier (e.g. TYPE_ERROR_MISSING_ARGUMENT)
        is_repairable — Whether the LLM self-healing pass should attempt a repair
        reason        — Concise human-readable reason for the failure
    """

    category: FailureCategory
    rule_id: str
    is_repairable: bool
    reason: str



# Deterministic pattern rules for classification ordered by specificity
_PATTERNS = [
    # Non-repairable infrastructure & security failures
    (
        FailureCategory.SANDBOX_UNAVAILABLE,
        "SANDBOX_UNAVAILABLE",
        re.compile(r"SANDBOX_UNAVAILABLE|connection refused", re.IGNORECASE),
        False,
        "Sandbox execution service unavailable",
    ),
    (
        FailureCategory.TIMEOUT,
        "TIMEOUT_EXCEEDED",
        re.compile(r"TimeoutExpired|wall-clock timeout", re.IGNORECASE),
        False,
        "Execution wall-clock timeout exceeded",
    ),
    (
        FailureCategory.SECURITY_ERROR,
        "SECURITY_VIOLATION",
        re.compile(r"security|permission denied", re.IGNORECASE),
        False,
        "Security restriction or permission error",
    ),

    # Repairable code & invocation errors
    (
        FailureCategory.TYPE_ERROR,
        "TYPE_ERROR_MISSING_ARGUMENT",
        re.compile(r"TypeError:.*missing.*required.*positional argument", re.IGNORECASE),
        True,
        "Missing required positional argument",
    ),
    (
        FailureCategory.TYPE_ERROR,
        "TYPE_ERROR_UNEXPECTED_KEYWORD",
        re.compile(r"TypeError:.*unexpected keyword argument", re.IGNORECASE),
        True,
        "Unexpected keyword argument",
    ),
    (
        FailureCategory.TYPE_ERROR,
        "TYPE_ERROR_ARGUMENT_COUNT",
        re.compile(r"TypeError:.*takes.*positional argument", re.IGNORECASE),
        True,
        "Positional argument count mismatch",
    ),
    (
        FailureCategory.TYPE_ERROR,
        "TYPE_ERROR_SIGNATURE",
        re.compile(r"TypeError:", re.IGNORECASE),
        True,
        "Function argument type or signature mismatch",
    ),
    (
        FailureCategory.MODULE_NOT_FOUND,
        "MODULE_NOT_FOUND",
        re.compile(r"ModuleNotFoundError", re.IGNORECASE),
        True,
        "Module import failed",
    ),
    (
        FailureCategory.IMPORT_ERROR,
        "IMPORT_SYMBOL_NOT_FOUND",
        re.compile(r"ImportError", re.IGNORECASE),
        True,
        "Symbol import failed",
    ),
    (
        FailureCategory.NAME_ERROR,
        "NAME_UNDEFINED",
        re.compile(r"NameError", re.IGNORECASE),
        True,
        "Undefined name reference",
    ),
    (
        FailureCategory.ATTRIBUTE_ERROR,
        "ATTRIBUTE_METHOD_NOT_FOUND",
        re.compile(r"AttributeError", re.IGNORECASE),
        True,
        "Attribute or method access error",
    ),
    (
        FailureCategory.SYNTAX_ERROR,
        "SYNTAX_ERROR",
        re.compile(r"SyntaxError", re.IGNORECASE),
        True,
        "Syntax error in test code",
    ),
    (
        FailureCategory.INDENTATION_ERROR,
        "INDENTATION_ERROR",
        re.compile(r"IndentationError", re.IGNORECASE),
        True,
        "Indentation error in test code",
    ),

    # Non-repairable domain logic assertion failures
    (
        FailureCategory.ASSERTION_ERROR,
        "ASSERTION_ERROR",
        re.compile(r"AssertionError", re.IGNORECASE),
        False,
        "Assertion expectation mismatch",
    ),
]


def classify_sandbox_failure(
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
) -> FailureClassification:
    """Classify a sandbox execution failure into a structured FailureClassification.

    Args:
        exit_code — Process exit code (0 = success, 1 = test failure, -1 = unavailable)
        stdout    — Captured stdout
        stderr    — Captured stderr traceback

    Returns:
        FailureClassification dataclass instance
    """
    if exit_code == 0:
        return FailureClassification(
            category=FailureCategory.UNKNOWN,
            rule_id="EXECUTION_SUCCESS",
            is_repairable=False,
            reason="Execution succeeded (no failure)",
        )

    combined_output = f"{stderr}\n{stdout}".strip()
    if not combined_output:
        return FailureClassification(
            category=FailureCategory.UNKNOWN,
            rule_id="EMPTY_OUTPUT",
            is_repairable=False,
            reason="Empty execution output",
        )

    for category, rule_id, pattern, is_repairable, default_reason in _PATTERNS:
        if pattern.search(combined_output):
            return FailureClassification(
                category=category,
                rule_id=rule_id,
                is_repairable=is_repairable,
                reason=default_reason,
            )

    return FailureClassification(
        category=FailureCategory.UNKNOWN,
        rule_id="UNKNOWN_FAILURE",
        is_repairable=False,
        reason="Unclassified test failure",
    )
