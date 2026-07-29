"""Empty Test Smell Rule for TestGen AI v2.2."""

import ast
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic
from app.services.smell_rules.base_rule import TestSmellRule


class EmptyTestRule(TestSmellRule):
    """Detects empty test functions with no executable statements or assertions."""

    __test__ = False

    @property
    def name(self) -> str:
        return "EMPTY_TEST"

    @property
    def severity(self) -> str:
        return "HIGH"

    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        effective_statements = []
        for stmt in func_node.body:
            if isinstance(stmt, ast.Pass):
                continue
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    continue
            effective_statements.append(stmt)

        if not effective_statements:
            return [
                TestSmellDiagnostic(
                    smell_type=TestSmellCategory.EMPTY_TEST,
                    test_name=func_node.name,
                    line_number=func_node.lineno,
                    severity=self.severity,
                    message=f"Test function '{func_node.name}' contains no executable statements or assertions.",
                    recommendation="Implement test assertions or remove empty test method.",
                )
            ]
        return []
