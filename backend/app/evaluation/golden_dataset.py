"""Golden Dataset Evaluation — Phase 4.

Provides utilities for evaluating generated test suites against a pre-defined
Golden Dataset. This is an INTERNAL evaluation tool for quality assurance —
it is not exposed through any public API.

Architecture design:
  GoldenRecord       — defines the expected properties of tests for one function.
  EvaluationResult   — pass/fail outcome for one (generation, golden) pair.
  EvaluationReport   — aggregated pass/fail summary over a full dataset.
  GoldenDatasetEvaluator — stateless service that evaluates GenerationResult
                           objects against a list of GoldenRecords.

Evaluation criteria (configurable per GoldenRecord):
  1. Test count within [min_test_count, max_test_count].
  2. All required_categories are present.
  3. All required_test_names are present (exact name match).

The GoldenRecord and EvaluationResult are dataclasses (no DB persistence).
Evaluation reports can be serialised to JSON for CI pipeline consumption.

Usage:
    golden = GoldenRecord(
        name="calculate_discount",
        min_test_count=4,
        max_test_count=12,
        required_categories=["happy_path", "edge_case"],
        required_test_names=["test_zero_discount"],
    )
    evaluator = GoldenDatasetEvaluator([golden])
    report = evaluator.evaluate(generation_result)
    print(report.pass_rate)   # e.g. 1.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Data definitions
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class GoldenRecord:
    """Expected properties for test generation targeting one source function.

    Fields:
        name:                Unique identifier (usually the function name).
        min_test_count:      Minimum acceptable test count (default 4).
        max_test_count:      Maximum acceptable test count (default 20).
        required_categories: Category strings that must appear in the suite
                             (e.g. ["happy_path", "edge_case"]).
        required_test_names: Exact test names that must be present.
        notes:               Free-text annotation for human reviewers.
    """

    name: str
    min_test_count: int = 4
    max_test_count: int = 20
    required_categories: list[str] = field(default_factory=list)
    required_test_names: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldenRecord":
        """Deserialise a GoldenRecord from a plain dict (JSON row)."""
        return cls(
            name=data["name"],
            min_test_count=int(data.get("min_test_count", 4)),
            max_test_count=int(data.get("max_test_count", 20)),
            required_categories=list(data.get("required_categories", [])),
            required_test_names=list(data.get("required_test_names", [])),
            notes=str(data.get("notes", "")),
        )


@dataclass
class EvaluationResult:
    """Outcome of evaluating one GenerationResult against one GoldenRecord.

    Fields:
        golden_name:            Name of the GoldenRecord evaluated.
        passed:                 True iff ALL criteria passed.
        test_count:             Actual number of tests generated.
        expected_min:           Golden min_test_count.
        expected_max:           Golden max_test_count.
        count_in_range:         Whether test_count is within [min, max].
        categories_found:       Category strings actually present in the suite.
        missing_categories:     Required categories absent from the suite.
        required_names_found:   Required test names actually present.
        missing_required_names: Required test names absent.
        confidence_score:       Overall confidence score (float).
        notes:                  Evaluation notes for human reviewers.
    """

    golden_name: str
    passed: bool
    test_count: int
    expected_min: int
    expected_max: int
    count_in_range: bool
    categories_found: list[str]
    missing_categories: list[str]
    required_names_found: list[str]
    missing_required_names: list[str]
    confidence_score: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for JSON reporting."""
        return {
            "golden_name": self.golden_name,
            "passed": self.passed,
            "test_count": self.test_count,
            "expected_range": [self.expected_min, self.expected_max],
            "count_in_range": self.count_in_range,
            "categories_found": self.categories_found,
            "missing_categories": self.missing_categories,
            "required_names_found": self.required_names_found,
            "missing_required_names": self.missing_required_names,
            "confidence_score": round(self.confidence_score, 4),
            "notes": self.notes,
        }


@dataclass
class EvaluationReport:
    """Aggregated evaluation report over a full dataset evaluation run.

    Fields:
        total:       Total number of (generation, golden) pairs evaluated.
        passed:      Number that passed all criteria.
        failed:      Number that failed at least one criterion.
        pass_rate:   passed / total (0.0 if total == 0).
        results:     Individual EvaluationResult objects (one per golden record).
        summary:     Aggregated metric dict for CI integration.
    """

    total: int
    passed: int
    failed: int
    pass_rate: float
    results: list[EvaluationResult]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the full report to a plain dict (JSON-safe)."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
            "summary": self.summary,
            "results": [r.to_dict() for r in self.results],
        }


# ──────────────────────────────────────────────────────────────────────────────
# Evaluator service
# ──────────────────────────────────────────────────────────────────────────────


class GoldenDatasetEvaluator:
    """Stateless evaluation service.

    Compares a GenerationResult (or any dict/object with the expected fields)
    against a list of GoldenRecords and produces an EvaluationReport.

    The evaluator is stateless — it holds only the list of GoldenRecords.
    Multiple calls to evaluate() are safe and produce independent reports.
    """

    def __init__(self, golden_records: list[GoldenRecord]) -> None:
        self._records = golden_records

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        generation_result,  # GenerationResult or compatible duck-type
    ) -> EvaluationReport:
        """Evaluate a generation result against all registered GoldenRecords.

        Args:
            generation_result: A GenerationResult (domain object) with fields:
                - test_suite.test_cases (list with .name and .category)
                - validation_warnings (list[str])
                - sandbox_result (optional, with .exit_code)

        Returns:
            EvaluationReport with per-record results and aggregate metrics.
        """
        from app.evaluation.confidence import calculate_confidence

        # Extract observable properties from the generation result
        test_cases = _extract_test_cases(generation_result)
        validation_warnings = _extract_warnings(generation_result)
        sandbox_exit_code = _extract_sandbox_exit(generation_result)

        actual_names = {tc.get("name", "") for tc in test_cases}
        actual_categories = {tc.get("category", "") for tc in test_cases}
        test_count = len(test_cases)

        # Calculate overall confidence for this result
        confidence = calculate_confidence(
            test_count=test_count,
            validation_warnings=validation_warnings,
            sandbox_exit_code=sandbox_exit_code,
        )

        results: list[EvaluationResult] = []
        for record in self._records:
            result = self._evaluate_one(
                record=record,
                actual_names=actual_names,
                actual_categories=actual_categories,
                test_count=test_count,
                confidence_score=confidence.overall,
            )
            results.append(result)
            logger.debug(
                "golden_eval_result",
                golden=record.name,
                passed=result.passed,
                test_count=test_count,
            )

        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        failed_count = total - passed_count
        pass_rate = (passed_count / total) if total > 0 else 0.0

        return EvaluationReport(
            total=total,
            passed=passed_count,
            failed=failed_count,
            pass_rate=pass_rate,
            results=results,
            summary={
                "test_count": test_count,
                "confidence_score": round(confidence.overall, 4),
                "confidence_grade": confidence.grade,
                "warning_count": len(validation_warnings),
                "sandbox_exit_code": sandbox_exit_code,
            },
        )

    def evaluate_dict(
        self,
        artifacts: dict[str, Any],
    ) -> EvaluationReport:
        """Evaluate a plain dict representation (e.g. from L2 cache).

        Args:
            artifacts: Dict with keys:
                - "test_cases": list of {"name": str, "category": str}
                - "validation_warnings": list[str]
                - "sandbox_exit_code": int | None

        Returns:
            EvaluationReport.
        """
        from app.evaluation.confidence import calculate_confidence

        test_cases = artifacts.get("test_cases", [])
        validation_warnings = artifacts.get("validation_warnings", [])
        sandbox_exit_code = artifacts.get("sandbox_exit_code")
        test_count = len(test_cases)

        actual_names = {tc.get("name", "") for tc in test_cases}
        actual_categories = {tc.get("category", "") for tc in test_cases}

        confidence = calculate_confidence(
            test_count=test_count,
            validation_warnings=validation_warnings,
            sandbox_exit_code=sandbox_exit_code,
        )

        results: list[EvaluationResult] = []
        for record in self._records:
            result = self._evaluate_one(
                record=record,
                actual_names=actual_names,
                actual_categories=actual_categories,
                test_count=test_count,
                confidence_score=confidence.overall,
            )
            results.append(result)

        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        failed_count = total - passed_count
        pass_rate = (passed_count / total) if total > 0 else 0.0

        return EvaluationReport(
            total=total,
            passed=passed_count,
            failed=failed_count,
            pass_rate=pass_rate,
            results=results,
            summary={
                "test_count": test_count,
                "confidence_score": round(confidence.overall, 4),
                "confidence_grade": confidence.grade,
                "warning_count": len(validation_warnings),
                "sandbox_exit_code": sandbox_exit_code,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_one(
        self,
        record: GoldenRecord,
        actual_names: set[str],
        actual_categories: set[str],
        test_count: int,
        confidence_score: float,
    ) -> EvaluationResult:
        """Evaluate one GoldenRecord against the generation result."""
        notes: list[str] = []

        # Criterion 1: test count in range
        count_ok = record.min_test_count <= test_count <= record.max_test_count
        if not count_ok:
            notes.append(
                f"Test count {test_count} outside expected range "
                f"[{record.min_test_count}, {record.max_test_count}]"
            )

        # Criterion 2: required categories present
        missing_cats = [c for c in record.required_categories if c not in actual_categories]
        if missing_cats:
            notes.append(f"Missing categories: {', '.join(missing_cats)}")

        # Criterion 3: required test names present
        missing_names = [n for n in record.required_test_names if n not in actual_names]
        if missing_names:
            notes.append(f"Missing required test names: {', '.join(missing_names)}")

        passed = count_ok and not missing_cats and not missing_names

        if record.notes:
            notes.append(f"Reviewer note: {record.notes}")

        return EvaluationResult(
            golden_name=record.name,
            passed=passed,
            test_count=test_count,
            expected_min=record.min_test_count,
            expected_max=record.max_test_count,
            count_in_range=count_ok,
            categories_found=sorted(actual_categories),
            missing_categories=missing_cats,
            required_names_found=[n for n in record.required_test_names if n in actual_names],
            missing_required_names=missing_names,
            confidence_score=confidence_score,
            notes=notes,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Dataset loading
# ──────────────────────────────────────────────────────────────────────────────


def load_golden_dataset(path: str) -> list[GoldenRecord]:
    """Load a Golden Dataset from a JSON file.

    File format (JSON array of objects):
    [
      {
        "name": "calculate_discount",
        "min_test_count": 4,
        "max_test_count": 12,
        "required_categories": ["happy_path", "edge_case"],
        "required_test_names": ["test_zero_discount"],
        "notes": "Price must never go negative."
      },
      ...
    ]

    Args:
        path: Absolute or relative path to the JSON file.

    Returns:
        List of GoldenRecord objects.

    Raises:
        FileNotFoundError if path does not exist.
        ValueError if the file is not valid JSON or missing required fields.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Golden dataset file not found: {path}")

    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Golden dataset must be a JSON array.")

    records = []
    for idx, item in enumerate(raw):
        try:
            records.append(GoldenRecord.from_dict(item))
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Invalid golden record at index {idx}: {exc}") from exc

    logger.info("golden_dataset_loaded", path=str(path), count=len(records))
    return records


# ──────────────────────────────────────────────────────────────────────────────
# Extraction helpers (duck-type compatible with GenerationResult)
# ──────────────────────────────────────────────────────────────────────────────


def _extract_test_cases(result) -> list[dict]:
    """Extract test cases from a GenerationResult or compatible object."""
    try:
        # GenerationResult.test_suite.test_cases (list of TestCase domain objects)
        cases = result.test_suite.test_cases
        return [
            {"name": tc.name, "category": getattr(tc, "category", "")}
            for tc in cases
        ]
    except AttributeError:
        pass

    try:
        # Dict representation from golden dataset
        return result.get("test_cases", [])
    except AttributeError:
        return []


def _extract_warnings(result) -> list[str]:
    """Extract validation warnings from a GenerationResult or dict."""
    try:
        return result.validation_warnings or []
    except AttributeError:
        try:
            return result.get("validation_warnings", [])
        except AttributeError:
            return []


def _extract_sandbox_exit(result) -> int | None:
    """Extract sandbox exit code from a GenerationResult or dict."""
    try:
        sr = result.sandbox_result
        if sr is None:
            return None
        return sr.exit_code
    except AttributeError:
        try:
            return result.get("sandbox_exit_code")
        except AttributeError:
            return None
