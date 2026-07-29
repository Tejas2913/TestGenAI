"""Duplicate Assertion Smell Rule for TestGen AI v2.2."""

import ast
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic
from app.services.smell_rules.base_rule import TestSmellRule


class DuplicateAssertionRule(TestSmellRule):
    """Detects repeated identical assertion expressions within a test function."""

    __test__ = False

    @property
    def name(self) -> str:
        return "DUPLICATE_ASSERTION"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        diagnostics: list[TestSmellDiagnostic] = []
        seen_expressions: set[str] = set()

        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                expr_dump = ast.dump(node.test)
                if expr_dump in seen_expressions:
                    diagnostics.append(
                        TestSmellDiagnostic(
                            smell_type=TestSmellCategory.DUPLICATE_ASSERTION,
                            test_name=func_node.name,
                            line_number=node.lineno,
                            severity=self.severity,
                            message=f"Function '{func_node.name}' contains duplicate assertion on line {node.lineno}.",
                            recommendation="Remove redundant duplicate assert statement.",
                        )
                    )
                else:
                    seen_expressions.add(expr_dump)

        return diagnostics
