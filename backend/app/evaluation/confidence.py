"""Confidence Scoring — Phase 4.

Calculates a deterministic confidence score for each completed generation
result. The score combines three architecture-defined signals into a single
float in [0.0, 1.0] plus a human-readable grade.

Architecture-defined signals and weights:
  sandbox_signal   (weight 0.40) — Did the generated tests pass execution?
  validation_signal (weight 0.30) — How clean was the validation output?
  test_count_signal (weight 0.30) — Is the test count within expected range?

Signal values:
  sandbox_signal:
    exit_code == 0   → 1.00  (tests passed)
    exit_code == 1   → 0.50  (tests ran but failed)
    exit_code == -1  → 0.00  (sandbox unavailable)
    None             → 0.60  (no sandbox — neutral, not penalised)

  validation_signal:
    0 warnings       → 1.00
    1 warning        → 0.80
    2 warnings       → 0.60
    3 warnings       → 0.40
    4 warnings       → 0.20
    ≥5 warnings      → 0.00

  test_count_signal:
    ≥6 and ≤12      → 1.00  (ideal range — maps to architecture's 8 targets)
    3-5 or 13-20    → 0.70  (acceptable range)
    1-2 or 21-30    → 0.40  (sparse or bloated)
    0 or >30        → 0.00  (degenerate)

Grades:
  overall ≥ 0.80  → HIGH
  overall ≥ 0.55  → MEDIUM
  overall < 0.55  → LOW

The calculation is DETERMINISTIC: identical inputs always produce identical
scores. No randomness, no LLM calls, no external state.

DO NOT add signals outside those defined above without architecture approval.

Usage:
    result = calculate_confidence(
        test_count=8,
        validation_warnings=[],
        sandbox_exit_code=0,
    )
    # result.overall == 1.0, result.grade == "HIGH"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ──────────────────────────────────────────────────────────────────────────────
# Signal constants (architecture-defined)
# ──────────────────────────────────────────────────────────────────────────────

_WEIGHT_SANDBOX = 0.40
_WEIGHT_VALIDATION = 0.30
_WEIGHT_TEST_COUNT = 0.30

_GRADE_HIGH_THRESHOLD = 0.80
_GRADE_MEDIUM_THRESHOLD = 0.55


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfidenceScore:
    """Immutable confidence score for a single generation result.

    Fields:
        overall:           Weighted score in [0.0, 1.0].
        grade:             "HIGH", "MEDIUM", or "LOW".
        sandbox_signal:    Raw sandbox signal value [0.0, 1.0].
        validation_signal: Raw validation signal value [0.0, 1.0].
        test_count_signal: Raw test count signal value [0.0, 1.0].
        test_count:        Actual number of tests generated.
        warning_count:     Number of validation warnings.
        sandbox_exit_code: Raw sandbox exit code (None if not executed).
    """

    overall: float
    grade: str
    sandbox_signal: float
    validation_signal: float
    test_count_signal: float
    test_count: int
    warning_count: int
    sandbox_exit_code: int | None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for API responses and logging."""
        return {
            "overall": round(self.overall, 4),
            "grade": self.grade,
            "signals": {
                "sandbox": round(self.sandbox_signal, 4),
                "validation": round(self.validation_signal, 4),
                "test_count": round(self.test_count_signal, 4),
            },
            "metadata": {
                "test_count": self.test_count,
                "warning_count": self.warning_count,
                "sandbox_exit_code": self.sandbox_exit_code,
            },
        }


# ──────────────────────────────────────────────────────────────────────────────
# Signal calculators (pure functions — deterministic)
# ──────────────────────────────────────────────────────────────────────────────


def _sandbox_signal(exit_code: int | None) -> float:
    """Map sandbox exit code to a signal value.

    Args:
        exit_code: Sandbox process exit code. None = not executed.

    Returns:
        Float in [0.0, 1.0].
    """
    if exit_code is None:
        return 0.60   # Neutral — sandbox not enabled
    if exit_code == 0:
        return 1.00   # All tests passed
    if exit_code == 1:
        return 0.50   # Tests ran but some failed
    # exit_code == -1 (SANDBOX_UNAVAILABLE) or other errors
    return 0.00


def _validation_signal(warning_count: int) -> float:
    """Map validation warning count to a signal value.

    Args:
        warning_count: Number of non-fatal validation warnings.

    Returns:
        Float in [0.0, 1.0].
    """
    if warning_count <= 0:
        return 1.00
    if warning_count == 1:
        return 0.80
    if warning_count == 2:
        return 0.60
    if warning_count == 3:
        return 0.40
    if warning_count == 4:
        return 0.20
    # ≥5 warnings
    return 0.00


def _test_count_signal(count: int) -> float:
    """Map test count to a signal value.

    Args:
        count: Number of test cases in the generated suite.

    Returns:
        Float in [0.0, 1.0].
    """
    if 6 <= count <= 12:
        return 1.00   # Ideal range (architecture targets 8)
    if (3 <= count <= 5) or (13 <= count <= 20):
        return 0.70   # Acceptable
    if (1 <= count <= 2) or (21 <= count <= 30):
        return 0.40   # Sparse or bloated
    # 0 or >30
    return 0.00


def _grade(score: float) -> str:
    """Convert a numeric score to a human-readable grade.

    Args:
        score: Weighted confidence in [0.0, 1.0].

    Returns:
        "HIGH", "MEDIUM", or "LOW".
    """
    if score >= _GRADE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= _GRADE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────


def calculate_confidence(
    test_count: int,
    validation_warnings: list[str],
    sandbox_exit_code: int | None,
) -> ConfidenceScore:
    """Calculate a deterministic confidence score for a generation result.

    This is the ONLY public function in this module. All inputs are derived
    from the GenerationResult and optional SandboxExecuteResponse — no
    external state or randomness is used.

    Args:
        test_count:          Number of test cases in the generated suite.
        validation_warnings: List of non-fatal validator warning strings.
        sandbox_exit_code:   Sandbox exit code (0=pass, 1=fail, -1=unavailable,
                             None=not executed).

    Returns:
        ConfidenceScore — immutable, fully deterministic.
    """
    s_sandbox = _sandbox_signal(sandbox_exit_code)
    s_validation = _validation_signal(len(validation_warnings))
    s_test_count = _test_count_signal(test_count)

    overall = (
        _WEIGHT_SANDBOX * s_sandbox
        + _WEIGHT_VALIDATION * s_validation
        + _WEIGHT_TEST_COUNT * s_test_count
    )
    # Clamp to [0.0, 1.0] to guard against floating-point edge cases
    overall = max(0.0, min(1.0, overall))

    return ConfidenceScore(
        overall=overall,
        grade=_grade(overall),
        sandbox_signal=s_sandbox,
        validation_signal=s_validation,
        test_count_signal=s_test_count,
        test_count=test_count,
        warning_count=len(validation_warnings),
        sandbox_exit_code=sandbox_exit_code,
    )
