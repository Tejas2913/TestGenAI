"""Unit tests for Phase 3 Self-Healing execution integration in JobEngine.

Verifies:
  - Successful sandbox executions bypass repair pass completely.
  - Non-recoverable failures (AssertionError, TimeoutExpired) bypass repair pass.
  - Recoverable failures (TypeError) trigger exactly ONE repair pass.
  - Repaired test code passing Python syntax validation runs ONCE in second sandbox.
  - Syntax validation failures or LLM exceptions return original generation immediately without second sandbox execution.
"""

from unittest.mock import MagicMock
import pytest

from app.sandbox.schemas import SandboxExecuteResponse
from app.services.job_engine import _self_heal


class DummyGeneration:
    """Mock Generation DB record."""

    def __init__(self, gen_id="gen-123", tests_code="def test_foo(): pass", source_code="def foo(): pass"):
        self.id = gen_id
        self.generated_tests_code = tests_code
        self.source_code = source_code
        self.prompt_version = "v1"
        self.sandbox_exit_code = None
        self.sandbox_stdout = None
        self.sandbox_stderr = None
        self.sandbox_duration_ms = None


class TestSelfHealExecutionFlow:
    """Phase 3 execution flow tests."""

    def test_successful_sandbox_bypasses_repair(self) -> None:
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = SandboxExecuteResponse(
            exit_code=0, stdout="1 passed", stderr="", duration_ms=120.0
        )
        mock_provider = MagicMock()
        mock_log = MagicMock()

        gen = DummyGeneration()
        result = _self_heal("job-1", gen, mock_sandbox, mock_provider, mock_log)

        assert result.repair_performed is False
        assert mock_sandbox.execute.call_count == 1
        assert mock_provider.generate.call_count == 0
        assert mock_log.info.call_count >= 1

    def test_non_repairable_failure_bypasses_repair(self) -> None:
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = SandboxExecuteResponse(
            exit_code=1, stdout="", stderr="AssertionError: assert 100 == 75", duration_ms=150.0
        )
        mock_provider = MagicMock()
        mock_log = MagicMock()

        gen = DummyGeneration()
        result = _self_heal("job-1", gen, mock_sandbox, mock_provider, mock_log)

        assert result.repair_performed is False
        assert mock_sandbox.execute.call_count == 1
        assert mock_provider.generate.call_count == 0

    def test_recoverable_failure_triggers_single_repair(self) -> None:
        mock_sandbox = MagicMock()
        # 1st run fails with TypeError, 2nd run passes
        mock_sandbox.execute.side_effect = [
            SandboxExecuteResponse(exit_code=1, stdout="", stderr="TypeError: calculate() missing 1 required positional argument", duration_ms=100.0),
            SandboxExecuteResponse(exit_code=0, stdout="1 passed", stderr="", duration_ms=110.0),
        ]
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "def test_foo(): assert calculate(10) == 20"
        mock_log = MagicMock()

        gen = DummyGeneration(tests_code="def test_foo(): calculate()")
        result = _self_heal("job-1", gen, mock_sandbox, mock_provider, mock_log)

        assert result.repair_performed is True
        assert result.repaired_code == "def test_foo(): assert calculate(10) == 20"
        assert result.sandbox_result.exit_code == 0
        assert mock_sandbox.execute.call_count == 2
        assert mock_provider.generate.call_count == 1

    def test_llm_failure_returns_original_generation(self) -> None:
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = SandboxExecuteResponse(
            exit_code=1, stdout="", stderr="TypeError: calculate() missing 1 argument", duration_ms=100.0
        )
        mock_provider = MagicMock()
        mock_provider.generate.side_effect = RuntimeError("API Rate Limit")
        mock_log = MagicMock()

        gen = DummyGeneration()
        result = _self_heal("job-1", gen, mock_sandbox, mock_provider, mock_log)

        assert result.repair_performed is True
        assert result.repair_success is False
        assert result.sandbox_result.exit_code == 1
        assert mock_sandbox.execute.call_count == 1
        assert mock_provider.generate.call_count == 1

    def test_syntax_validation_failure_bypasses_second_sandbox(self) -> None:
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = SandboxExecuteResponse(
            exit_code=1, stdout="", stderr="TypeError: missing argument", duration_ms=100.0
        )
        mock_provider = MagicMock()
        # LLM returns invalid Python syntax
        mock_provider.generate.return_value = "def test_foo(invalid syntax here"
        mock_log = MagicMock()

        gen = DummyGeneration()
        result = _self_heal("job-1", gen, mock_sandbox, mock_provider, mock_log)

        assert result.repair_performed is True
        assert result.repair_success is False
        assert mock_sandbox.execute.call_count == 1  # 2nd sandbox run NEVER called!
        assert mock_provider.generate.call_count == 1
