"""Self-Healing Domain Model.

Represents the execution outcome of the Self-Healing repair workflow.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.failure_classifier import FailureClassification


@dataclass
class SelfHealingResult:
    """Execution outcome of the Self-Healing repair workflow.

    Fields:
        repair_performed   — Whether a surgical repair pass was attempted
        repair_success     — Whether repair was attempted AND second sandbox execution passed (exit_code == 0)
        repair_count       — Number of repair attempts (0 or 1)
        repair_duration_ms — Measured wall-clock time spent on the repair workflow in ms
        repaired_code      — The validated repaired test code string (or None if no repair)
        sandbox_result     — Final sandbox execution response object
        initial_result     — Initial sandbox execution response object
        classification     — Failure classification result (or None if success)
    """

    repair_performed: bool = False
    repair_success: bool = False
    repair_count: int = 0
    repair_duration_ms: float = 0.0
    repaired_code: str | None = None
    sandbox_result: Any | None = None
    initial_result: Any | None = None
    classification: FailureClassification | None = None
