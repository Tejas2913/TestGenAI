"""Test Smell Diagnostic Domain Models for TestGen AI v2.2.

Provides domain entities representing static test anti-pattern categories,
individual diagnostic findings, and aggregated smell scan reports.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class TestSmellCategory(StrEnum):
    """Catalog of static test anti-patterns and code smells."""

    __test__ = False

    ASSERTION_ROULETTE = "ASSERTION_ROULETTE"
    DUPLICATE_ASSERTION = "DUPLICATE_ASSERTION"
    EMPTY_TEST = "EMPTY_TEST"
    MAGIC_NUMBER = "MAGIC_NUMBER"
    RED_HERRING = "RED_HERRING"
    VERBOSE_TEST = "VERBOSE_TEST"
    CONDITIONAL_LOGIC = "CONDITIONAL_LOGIC"


@dataclass
class TestSmellDiagnostic:
    """Diagnostic detail for an individual detected test smell."""

    __test__ = False

    smell_type: TestSmellCategory
    test_name: str
    line_number: int
    severity: str
    message: str
    recommendation: str


@dataclass
class TestSmellSummary:
    """Aggregated report of all test smells detected in a test suite."""

    __test__ = False

    total_smells: int = 0
    high_severity_count: int = 0
    medium_severity_count: int = 0
    low_severity_count: int = 0
    diagnostics: list[TestSmellDiagnostic] = field(default_factory=list)
