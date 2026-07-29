"""TestGen AI v2.3 — Repository Context Engine Unit Tests (Phase 3).

Verifies AST repository indexing, directory tree scanning, symbol extraction,
syntax error handling, test discovery, dependency parsing, framework detection,
RepositoryContext population, and PlannerAgent integration.
"""

import os
import tempfile
import pytest

from app.agents.planner import PlannerAgent
from app.domain.v23_models import AgentWorkflowContext, GenerationRequest, RepositoryContext, TestPlan
from app.infrastructure.indexers.repository_index import RepositoryContextIndex
from app.workflows.agent_workflow import AgentWorkflow


class TestASTSymbolExtraction:
    """Tests for single source code AST symbol extraction."""

    def test_single_source_symbol_extraction(self):
        code = """
import os
import sys
from typing import List, Optional

class DataProcessor:
    \"\"\"Processes data batches.\"\"\"
    def __init__(self, name: str):
        self.name = name

    async def process_async(self, items: List[int]) -> bool:
        \"\"\"Process items asynchronously.\"\"\"
        return True

def standalone_function(x: int) -> int:
    return x * 2
"""
        index = RepositoryContextIndex()
        ctx = index.build_context(code)

        assert isinstance(ctx, RepositoryContext)
        assert "os" in ctx.imports
        assert "sys" in ctx.imports
        assert "DataProcessor" in ctx.custom_types
        assert len(ctx.classes) == 1
        assert ctx.classes[0]["name"] == "DataProcessor"
        assert ctx.classes[0]["docstring"] == "Processes data batches."

        assert len(ctx.functions) == 3
        func_names = [f["name"] for f in ctx.functions]
        assert "process_async" in func_names
        assert "standalone_function" in func_names
        assert "__init__" in func_names

        async_func = next(f for f in ctx.functions if f["name"] == "process_async")
        assert async_func["is_async"] is True

    def test_pytest_fixture_extraction(self):
        code = """
import pytest

@pytest.fixture
def sample_fixture():
    return {"key": "value"}
"""
        index = RepositoryContextIndex()
        ctx = index.build_context(code)

        assert "sample_fixture" in ctx.pytest_fixtures
        assert "Pytest" in ctx.frameworks

    def test_syntax_error_graceful_handling(self):
        code = "def broken_syntax(:"
        index = RepositoryContextIndex()
        ctx = index.build_context(code)

        assert isinstance(ctx, RepositoryContext)
        assert ctx.indexing_summary["failed_files"] == 0 or ctx.statistics["total_functions"] == 0


class TestDirectoryScanningAndFrameworkDetection:
    """Tests for directory tree scanning, test discovery, and framework detection."""

    def test_directory_indexing_with_temp_repo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subdirectories
            app_dir = os.path.join(tmpdir, "app")
            tests_dir = os.path.join(tmpdir, "tests")
            venv_dir = os.path.join(tmpdir, ".venv")
            os.makedirs(app_dir)
            os.makedirs(tests_dir)
            os.makedirs(venv_dir)

            # 1. Create main.py (FastAPI app)
            main_py = os.path.join(app_dir, "main.py")
            with open(main_py, "w") as f:
                f.write("""
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

@app.get("/health")
def health():
    return {"status": "ok"}
""")

            # 2. Create test file
            test_py = os.path.join(tests_dir, "test_main.py")
            with open(test_py, "w") as f:
                f.write("""
import pytest

def test_health():
    assert True
""")

            # 3. Create ignored venv file
            venv_py = os.path.join(venv_dir, "ignored.py")
            with open(venv_py, "w") as f:
                f.write("def ignored(): pass")

            # 4. Create requirements.txt
            req_file = os.path.join(tmpdir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("fastapi==0.100.0\nuvicorn>=0.20.0\npytest\n")

            index = RepositoryContextIndex()
            ctx = index.build_context(tmpdir)

            # Assertions
            assert ctx.metadata["root_path"] == os.path.abspath(tmpdir)
            assert ctx.metadata["source_files_count"] == 2  # main.py and test_main.py (ignored.py excluded)
            assert "fastapi" in ctx.dependencies
            assert "uvicorn" in ctx.dependencies
            assert "pytest" in ctx.dependencies
            assert "FastAPI" in ctx.frameworks
            assert "Pytest" in ctx.frameworks
            assert len(ctx.existing_tests) == 1
            assert ctx.existing_tests[0]["file_path"].replace("\\", "/").endswith("tests/test_main.py")


class TestPlannerAgentIntegration:
    """Tests for PlannerAgent integration with RepositoryContextIndex."""

    def test_planner_agent_indexes_and_attaches_context(self):
        planner = PlannerAgent()
        code = """
import os

def calculate_sum(a: int, b: int) -> int:
    \"\"\"Calculates sum.\"\"\"
    return a + b
"""
        req = GenerationRequest(source_code=code)
        wf_ctx = AgentWorkflowContext(request=req)

        res_ctx = planner.run(wf_ctx)

        assert isinstance(res_ctx.repository_context, RepositoryContext)
        assert "os" in res_ctx.repository_context.imports
        assert len(res_ctx.repository_context.functions) == 1
        assert res_ctx.repository_context.functions[0]["name"] == "calculate_sum"
        assert isinstance(res_ctx.test_plan, TestPlan)
        assert len(res_ctx.test_plan.target_functions) >= 1

    def test_full_workflow_with_repository_context(self):
        wf = AgentWorkflow()
        req = GenerationRequest(source_code="def process(): pass")
        ctx = wf.execute_workflow(req)

        assert ctx.repository_context is not None
        assert ctx.repository_context.metadata["total_files"] >= 1
        assert len(ctx.reasoning_traces) == 4
        assert "RepositoryContext" in ctx.reasoning_traces[0].rationale_summary
