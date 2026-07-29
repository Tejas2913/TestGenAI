"""Assertion Roulette Smell Rule for TestGen AI v2.2."""

import ast
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic
from app.services.smell_rules.base_rule import TestSmellRule


class AssertionRouletteRule(TestSmellRule):
    """Detects test functions with multiple assertions lacking custom failure messages."""

    __test__ = False

    @property
    def name(self) -> str:
        return "ASSERTION_ROULETTE"

    @property
    def severity(self) -> str:
        return "LOW"

    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        assert_nodes = [node for node in ast.walk(func_node) if isinstance(node, ast.Assert)]
        if len(assert_nodes) <= 1:
            return []

        unlabeled_asserts = [a for a in assert_nodes if a.msg is None]
        if unlabeled_asserts:
            first_unlabeled = unlabeled_asserts[0]
            return [
                TestSmellDiagnostic(
                    smell_type=TestSmellCategory.ASSERTION_ROULETTE,
                    test_name=func_node.name,
                    line_number=first_unlabeled.lineno,
                    severity=self.severity,
                    message=f"Function '{func_node.name}' contains {len(assert_nodes)} assertions without custom messages.",
                    recommendation="Add descriptive custom failure messages to distinguish failing assertions.",
                )
            ]
        return []
