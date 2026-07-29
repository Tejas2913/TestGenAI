"""Comprehensive unit test suite for DockerMutationExecutor & MutationExecution subsystem (Phase 5).

Verifies:
  - Classification of KILLED mutants (tests fail on mutated code, exit_code != 0).
  - Classification of SURVIVED mutants (tests pass despite mutated code, exit_code == 0).
  - Classification of TIMEOUT mutants (exit_code == 124 or timeout in stderr).
  - Classification of ERROR / runtime exceptions.
  - Calculation of mutation score percentage: (killed / executable) * 100.
  - Partial failure resilience (campaign continues executing remaining mutants).
  - Decoupled execution strategy architecture.
"""

from unittest.mock import MagicMock
import pytest

from app.domain.mutation import MutantResult, MutationCategory
from app.sandbox.schemas import (
    SANDBOX_UNAVAILABLE_EXIT_CODE,
    SandboxExecuteResponse,
)
from app.services.mutation_execution.docker_executor import DockerMutationExecutor
from app.services.mutation_runner import MutationRunner


class TestMutationExecutionSuite:
    """Test suite for DockerMutationExecutor strategy and campaign execution."""

    @pytest.fixture
    def executor(self) -> DockerMutationExecutor:
        """Provide DockerMutationExecutor instance."""
        return DockerMutationExecutor()

    def test_executor_metadata_and_support(self, executor: DockerMutationExecutor) -> None:
        """Verify executor_name and supports_environment."""
        assert executor.executor_name == "docker"
        assert executor.supports_environment() is True

    def test_apply_mutation_line_replacement(self, executor: DockerMutationExecutor) -> None:
        """Verify line replacement preserves indentation."""
        source = "def foo():\n    return a == b\n"
        mutant = MutantResult(
            mutant_id="MUT_1",
            category=MutationCategory.COMPARISON_OPERATOR,
            description="Replaced == with !=",
            original_line=2,
            mutated_line_content="return a != b",
            status="UNTESTED",
        )

        mutated_code = executor.apply_mutation(source, mutant)
        assert "    return a != b" in mutated_code

    def test_killed_mutant_classification(self, executor: DockerMutationExecutor) -> None:
        """Verify exit_code != 0 classifies mutant as KILLED."""
        mock_client = MagicMock()
        mock_client.execute.return_value = SandboxExecuteResponse(
            exit_code=1, stdout="FAILED test_foo.py", stderr="", duration_ms=45.0
        )

        source = "def add(a, b): return a + b"
        test = "def test_add(): assert add(2, 3) == 5"
        mutant = MutantResult(
            mutant_id="MUT_KILLED",
            category=MutationCategory.BINARY_OPERATOR,
            description="Replaced + with -",
            original_line=1,
            mutated_line_content="def add(a, b): return a - b",
            status="UNTESTED",
        )

        res = executor.execute_mutant(
            mutant=mutant,
            source_code=source,
            test_code=test,
            sandbox_client=mock_client,
        )

        assert res.status == "KILLED"
        assert res.killing_test == "pytest"
        assert res.execution_time_ms > 0

    def test_survived_mutant_classification(self, executor: DockerMutationExecutor) -> None:
        """Verify exit_code == 0 classifies mutant as SURVIVED."""
        mock_client = MagicMock()
        mock_client.execute.return_value = SandboxExecuteResponse(
            exit_code=0, stdout="PASSED", stderr="", duration_ms=30.0
        )

        source = "def add(a, b): return a + b"
        test = "def test_add(): pass"
        mutant = MutantResult(
            mutant_id="MUT_SURVIVED",
            category=MutationCategory.BINARY_OPERATOR,
            description="Replaced + with -",
            original_line=1,
            mutated_line_content="def add(a, b): return a - b",
            status="UNTESTED",
        )

        res = executor.execute_mutant(
            mutant=mutant,
            source_code=source,
            test_code=test,
            sandbox_client=mock_client,
        )

        assert res.status == "SURVIVED"
        assert res.killing_test is None

    def test_timeout_mutant_classification(self, executor: DockerMutationExecutor) -> None:
        """Verify exit_code 124 classifies mutant as TIMEOUT."""
        mock_client = MagicMock()
        mock_client.execute.return_value = SandboxExecuteResponse(
            exit_code=124, stdout="", stderr="Command timed out after 15s", duration_ms=15000.0
        )

        mutant = MutantResult(
            mutant_id="MUT_TIMEOUT",
            category=MutationCategory.BINARY_OPERATOR,
            description="Timeout mutation",
            original_line=1,
            mutated_line_content="while True: pass",
            status="UNTESTED",
        )

        res = executor.execute_mutant(
            mutant=mutant,
            source_code="pass",
            test_code="pass",
            sandbox_client=mock_client,
        )

        assert res.status == "TIMEOUT"

    def test_error_mutant_classification(self, executor: DockerMutationExecutor) -> None:
        """Verify sidecar error / exception classifies mutant as ERROR."""
        mock_client = MagicMock()
        mock_client.execute.return_value = SandboxExecuteResponse(
            exit_code=SANDBOX_UNAVAILABLE_EXIT_CODE,
            stdout="",
            stderr="Sandbox unavailable",
            duration_ms=0.0,
        )

        mutant = MutantResult(
            mutant_id="MUT_ERROR",
            category=MutationCategory.BINARY_OPERATOR,
            description="Error mutation",
            original_line=1,
            mutated_line_content="syntax error",
            status="UNTESTED",
        )

        res = executor.execute_mutant(
            mutant=mutant,
            source_code="pass",
            test_code="pass",
            sandbox_client=mock_client,
        )

        assert res.status == "ERROR"

    def test_campaign_execution_and_score_calculation(
        self, executor: DockerMutationExecutor
    ) -> None:
        """Verify full campaign execution calculates mutation score correctly.

        1 Killed, 1 Survived -> 1 / 2 = 50.0% score.
        """
        mock_client = MagicMock()
        mock_client.execute.side_effect = [
            SandboxExecuteResponse(exit_code=1, stdout="FAIL", stderr="", duration_ms=10.0),
            SandboxExecuteResponse(exit_code=0, stdout="PASS", stderr="", duration_ms=10.0),
        ]

        m1 = MutantResult(
            mutant_id="M1",
            category=MutationCategory.BINARY_OPERATOR,
            description="M1",
            original_line=1,
            mutated_line_content="return a - b",
            status="UNTESTED",
        )
        m2 = MutantResult(
            mutant_id="M2",
            category=MutationCategory.BINARY_OPERATOR,
            description="M2",
            original_line=1,
            mutated_line_content="return a * b",
            status="UNTESTED",
        )

        summary = executor.execute_campaign(
            mutants=[m1, m2],
            source_code="def f(a, b): return a + b",
            test_code="def test_f(): assert f(2, 3) == 5",
            sandbox_client=mock_client,
        )

        assert summary.total_mutants == 2
        assert summary.killed_mutants == 1
        assert summary.survived_mutants == 1
        assert summary.mutation_score_pct == 50.0
        assert summary.duration_ms >= 0.0

    def test_partial_failure_resilience_in_campaign(
        self, executor: DockerMutationExecutor
    ) -> None:
        """Verify unexpected exception in one mutant does not abort remaining campaign."""
        mock_client = MagicMock()
        mock_client.execute.side_effect = [
            RuntimeError("Unexpected client crash"),
            SandboxExecuteResponse(exit_code=1, stdout="FAIL", stderr="", duration_ms=10.0),
        ]

        m1 = MutantResult("M1", MutationCategory.BINARY_OPERATOR, "M1", 1, "m1", "UNTESTED")
        m2 = MutantResult("M2", MutationCategory.BINARY_OPERATOR, "M2", 1, "m2", "UNTESTED")

        summary = executor.execute_campaign(
            mutants=[m1, m2],
            source_code="def f(): pass",
            test_code="def test_f(): pass",
            sandbox_client=mock_client,
        )

        assert summary.total_mutants == 2
        assert summary.killed_mutants == 1
        assert summary.incompatible_mutants == 1
        assert summary.mutation_score_pct == 100.0  # 1 killed / 1 executable

    def test_mutation_runner_execution_pass_integration(self) -> None:
        """Verify MutationRunner delegates execution pass to executor when sandbox_client is provided."""
        mock_client = MagicMock()
        mock_client.execute.return_value = SandboxExecuteResponse(
            exit_code=1, stdout="FAIL", stderr="", duration_ms=10.0
        )

        runner = MutationRunner()
        code = "def f(a, b): return a == b"
        test = "def test_f(): assert f(1, 1) is True"

        summary = runner.execute_mutation_pass(
            source_code=code,
            test_code=test,
            sandbox_client=mock_client,
        )

        assert summary.total_mutants >= 1
        assert summary.killed_mutants >= 1
        assert summary.mutation_score_pct > 0.0
