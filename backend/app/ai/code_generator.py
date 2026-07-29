"""Generates pytest source code from a TestSuite using Jinja2 templates."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.domain.test_suite import TestSuite

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class CodeGenerator:
    """Renders validated TestSuites into executable test source code.

    Uses Jinja2 templates stored in app/ai/templates/. The framework
    parameter selects the template file (e.g. "pytest" loads pytest.py.j2).
    New templates can be added without changing generator logic.
    """

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._templates_dir = templates_dir or _TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def generate(self, test_suite: TestSuite, framework: str = "pytest") -> str:
        """Render a TestSuite into test source code for the given framework.

        Args:
            test_suite: The validated test suite to render.
            framework: Template name to use (maps to {framework}.py.j2).

        Returns:
            Complete, executable test source code as a string.
        """
        # Deduplicate imports and remove 'import pytest' since it is
        # unconditionally present in the template.
        clean_imports = set()
        for imp in test_suite.imports:
            imp = imp.strip()
            if imp and imp != "import pytest":
                clean_imports.add(imp)
        
        # Explicitly import the analyzed function
        clean_imports.add(f"from main import {test_suite.function_name}")
        final_imports = sorted(list(clean_imports))

        # Reconstruct assertions reliably to fix LLM hallucination of function 
        # names, ensure JSON arrays are correctly formatted as lists, and
        # apply the multi-line context manager style for exception testing.
        for tc in test_suite.test_cases:
            # Use keyword arguments to ensure ordering doesn't matter
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in tc.inputs.items())
            call_str = f"{test_suite.function_name}({args_str})"

            if isinstance(tc.expected_output, str) and tc.expected_output.startswith("raises "):
                exc_type = tc.expected_output[7:].strip()
                # 8 spaces of indentation so it aligns perfectly inside the template
                tc.assertions = [f"with pytest.raises({exc_type}):\n        {call_str}"]
            else:
                tc.assertions = [f"assert {call_str} == {repr(tc.expected_output)}"]

        template = self._env.get_template(f"{framework}.py.j2")
        return template.render(
            function_name=test_suite.function_name,
            test_cases=test_suite.test_cases,
            imports=final_imports,
            setup_code=test_suite.setup_code,
        )
