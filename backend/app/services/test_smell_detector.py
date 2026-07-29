"""Test Smell Detector Orchestrator Service for TestGen AI v2.2.

Pure orchestrator that parses test code AST, discovers test functions, and delegates
smell checking to a registry of isolated TestSmellRule instances (Open/Closed Principle).
"""

import ast
import structlog

from app.core.config import settings
from app.domain.test_smell import (
    TestSmellDiagnostic,
    TestSmellSummary,
)
from app.services.smell_rules import DEFAULT_SMELL_RULES, TestSmellRule

logger = structlog.get_logger(__name__)


class TestSmellDetector:
    """Orchestrator for static AST test smell detection using registered TestSmellRule strategies."""

    __test__ = False

    def __init__(
        self,
        rules: list[TestSmellRule] | None = None,
        max_lines: int | None = None,
    ) -> None:
        """Initialize detector orchestrator with registered smell rules and max lines limit."""
        self.rules: list[TestSmellRule] = rules if rules is not None else DEFAULT_SMELL_RULES
        self.max_lines = (
            max_lines
            if max_lines is not None
            else getattr(settings, "MAX_TEST_FUNCTION_LINES", 50)
        )

    def detect(self, test_code: str) -> TestSmellSummary:
        """Perform static AST analysis on python test code and return aggregated smell summary.

        Never executes code. Safe against syntax and parse errors.
        """
        if not test_code or not test_code.strip():
            return TestSmellSummary(
                total_smells=0,
                high_severity_count=0,
                medium_severity_count=0,
                low_severity_count=0,
                diagnostics=[],
            )

        try:
            tree = ast.parse(test_code)
        except Exception as exc:
            logger.warning("test_smell_parse_error", error=str(exc))
            return TestSmellSummary(
                total_smells=0,
                high_severity_count=0,
                medium_severity_count=0,
                low_severity_count=0,
                diagnostics=[],
            )

        diagnostics: list[TestSmellDiagnostic] = []

        # Find test functions (or all functions if no test_ prefix exists)
        func_nodes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        test_funcs = [
            f for f in func_nodes if f.name.startswith("test_") or f.name.startswith("test")
        ]
        if not test_funcs and func_nodes:
            test_funcs = func_nodes

        for func in test_funcs:
            for rule in self.rules:
                diagnostics.extend(rule.detect(func, max_lines=self.max_lines))

        high_count = sum(1 for d in diagnostics if d.severity == "HIGH")
        med_count = sum(1 for d in diagnostics if d.severity == "MEDIUM")
        low_count = sum(1 for d in diagnostics if d.severity == "LOW")

        return TestSmellSummary(
            total_smells=len(diagnostics),
            high_severity_count=high_count,
            medium_severity_count=med_count,
            low_severity_count=low_count,
            diagnostics=diagnostics,
        )

    def analyze_test_smells(self, test_code: str) -> TestSmellSummary:
        """Alias for detect() providing interface compatibility."""
        return self.detect(test_code)
