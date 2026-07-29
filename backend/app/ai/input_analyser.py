"""Static analysis of Python source code using the ast module."""

import ast

from app.domain.code_metadata import CodeMetadata
from app.domain.parameter import ParameterInfo
from app.exceptions import ValidationException


class InputAnalyser:
    """Extracts structured metadata from Python function source code."""

    def analyse(self, source_code: str) -> CodeMetadata:
        """Parse source code and return metadata for the first function found."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError as exc:
            raise ValidationException(
                detail=f"Failed to parse source code: {exc.msg}"
            ) from exc

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_name = self._find_class_context(tree, node)
                return self._extract_metadata(node, class_name, source_code)

        raise ValidationException(
            detail="No function definition found in the provided source code"
        )

    def _extract_metadata(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str | None,
        source_code: str,
    ) -> CodeMetadata:
        """Build CodeMetadata from an AST function node."""
        return CodeMetadata(
            function_name=node.name,
            parameters=self._extract_parameters(node),
            return_type=self._extract_annotation(node.returns),
            docstring=ast.get_docstring(node),
            class_name=class_name,
            decorators=self._extract_decorators(node),
            source_code=source_code,
        )

    def _extract_parameters(self, node: ast.FunctionDef) -> list[ParameterInfo]:
        """Extract parameter names, type hints, and defaults from the signature."""
        params: list[ParameterInfo] = []
        args = node.args

        defaults_offset = len(args.args) - len(args.defaults)

        for index, arg in enumerate(args.args):
            if arg.arg == "self" or arg.arg == "cls":
                continue

            default_index = index - defaults_offset
            default_value = None
            if default_index >= 0:
                default_value = ast.unparse(args.defaults[default_index])

            params.append(
                ParameterInfo(
                    name=arg.arg,
                    type_hint=self._extract_annotation(arg.annotation),
                    default_value=default_value,
                )
            )

        return params

    def _extract_annotation(self, node: ast.expr | None) -> str | None:
        """Convert an AST annotation node to its string representation."""
        if node is None:
            return None
        return ast.unparse(node)

    def _extract_decorators(self, node: ast.FunctionDef) -> list[str]:
        """Extract decorator names from the function definition."""
        return [ast.unparse(decorator) for decorator in node.decorator_list]

    def _find_class_context(
        self, tree: ast.Module, target: ast.FunctionDef
    ) -> str | None:
        """Determine if the function is defined inside a class."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in ast.walk(node):
                    if child is target:
                        return node.name
        return None
