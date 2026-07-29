"""Verbose Test Smell Rule for TestGen AI v2.2."""

import ast
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic
from app.services.smell_rules.base_rule import TestSmellRule


class VerboseTestRule(TestSmellRule):
    """Detects test functions exceeding a configurable line threshold."""

    __test__ = False

    @property
    def name(self) -> str:
        return "VERBOSE_TEST"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        end_line = getattr(func_node, "end_lineno", func_node.lineno)
        line_count = end_line - func_node.lineno + 1

        if line_count > max_lines:
            return [
                TestSmellDiagnostic(
                    smell_type=TestSmellCategory.VERBOSE_TEST,
                    test_name=func_node.name,
                    line_number=func_node.lineno,
                    severity=self.severity,
                    message=f"Test function '{func_node.name}' is too long ({line_count} lines, threshold: {max_lines}).",
                    recommendation="Refactor large test method into smaller, focused single-responsibility unit tests.",
                )
            ]
        return []
