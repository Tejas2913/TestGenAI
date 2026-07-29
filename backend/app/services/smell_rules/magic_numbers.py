"""Magic Numbers Smell Rule for TestGen AI v2.2."""

import ast
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic
from app.services.smell_rules.base_rule import TestSmellRule

ALLOWED_NUMERIC_CONSTANTS = {-1, 0, 1, -1.0, 0.0, 1.0}


class MagicNumbersRule(TestSmellRule):
    """Detects unnamed numeric literals used directly in test assertions."""

    __test__ = False

    @property
    def name(self) -> str:
        return "MAGIC_NUMBER"

    @property
    def severity(self) -> str:
        return "LOW"

    def detect(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        max_lines: int = 50,
    ) -> list[TestSmellDiagnostic]:
        diagnostics: list[TestSmellDiagnostic] = []
        reported_lines: set[int] = set()

        for node in ast.walk(func_node):
            if isinstance(node, ast.Assert):
                for child in ast.walk(node.test):
                    if isinstance(child, ast.Constant):
                        val = child.value
                        if (
                            isinstance(val, (int, float))
                            and not isinstance(val, bool)
                            and val not in ALLOWED_NUMERIC_CONSTANTS
                        ):
                            line_no = getattr(child, "lineno", node.lineno)
                            if line_no not in reported_lines:
                                reported_lines.add(line_no)
                                diagnostics.append(
                                    TestSmellDiagnostic(
                                        smell_type=TestSmellCategory.MAGIC_NUMBER,
                                        test_name=func_node.name,
                                        line_number=line_no,
                                        severity=self.severity,
                                        message=f"Function '{func_node.name}' uses magic number {val} directly in assertion on line {line_no}.",
                                        recommendation="Extract numeric literal into a named constant or descriptive variable.",
                                    )
                                )
        return diagnostics
