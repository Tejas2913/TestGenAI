"""Conditional Logic Smell Rule for TestGen AI v2.2."""

import ast
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic
from app.services.smell_rules.base_rule import TestSmellRule


class ConditionalLogicRule(TestSmellRule):
    """Detects control flow statements (If, For, While, Match) inside unit tests."""

    __test__ = False

    @property
    def name(self) -> str:
        return "CONDITIONAL_LOGIC"

    @property
    def severity(self) -> str:
        return "MEDIUM"

    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        diagnostics: list[TestSmellDiagnostic] = []
        control_nodes = (ast.If, ast.For, ast.While, ast.IfExp)
        if hasattr(ast, "Match"):
            control_nodes = (*control_nodes, ast.Match)  # type: ignore[assignment]

        for node in ast.walk(func_node):
            if isinstance(node, control_nodes):
                stmt_type = type(node).__name__
                diagnostics.append(
                    TestSmellDiagnostic(
                        smell_type=TestSmellCategory.CONDITIONAL_LOGIC,
                        test_name=func_node.name,
                        line_number=node.lineno,
                        severity=self.severity,
                        message=f"Function '{func_node.name}' contains conditional or looping logic ({stmt_type}) on line {node.lineno}.",
                        recommendation="Avoid control flow inside unit tests; split conditional branches into separate test methods.",
                    )
                )
        return diagnostics
