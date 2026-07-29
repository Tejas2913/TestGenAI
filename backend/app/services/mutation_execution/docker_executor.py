"""Docker-based Mutation Execution Strategy for TestGen AI v2.2.

Executes generated mutants in isolated Sandbox sidecar containers, parses execution
outcomes (KILLED, SURVIVED, TIMEOUT, ERROR), and computes mutation score percentage.
"""

import time
from typing import Any
import structlog

from app.core.config import settings
from app.domain.mutation import MutantResult, MutationSummary
from app.sandbox.client import SandboxClient
from app.sandbox.schemas import (
    SANDBOX_UNAVAILABLE_EXIT_CODE,
    SandboxExecuteRequest,
)
from app.services.mutation_execution.base_executor import MutationExecutor

logger = structlog.get_logger(__name__)


class DockerMutationExecutor(MutationExecutor):
    """Executes mutants using isolated SandboxClient sidecar containers."""

    __test__ = False

    def __init__(self, default_client: Any = None) -> None:
        """Initialize executor with optional default SandboxClient."""
        self.default_client = default_client

    @property
    def executor_name(self) -> str:
        return "docker"

    def supports_environment(self) -> bool:
        """Check whether Sandbox sidecar execution environment is enabled."""
        return getattr(settings, "ENABLE_SANDBOX", True)

    def apply_mutation(self, source_code: str, mutant: MutantResult) -> str:
        """Apply a single line mutation replacement into source code."""
        lines = source_code.splitlines()
        target_idx = mutant.original_line - 1

        if 0 <= target_idx < len(lines):
            orig_line = lines[target_idx]
            # Preserve leading indentation whitespace
            indent = orig_line[: len(orig_line) - len(orig_line.lstrip())]
            lines[target_idx] = indent + mutant.mutated_line_content.strip()
            return "\n".join(lines)

        return source_code

    def execute_mutant(
        self,
        mutant: MutantResult,
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
        timeout_seconds: int = 15,
    ) -> MutantResult:
        """Execute test suite against a single mutated source code variant in Sandbox."""
        client = sandbox_client or self.default_client or SandboxClient()
        mutated_source = self.apply_mutation(source_code, mutant)

        request = SandboxExecuteRequest(
            code=test_code,
            source_code=mutated_source,
            timeout_seconds=timeout_seconds,
        )

        start_time = time.monotonic()

        try:
            response = client.execute(request)
            duration_ms = (time.monotonic() - start_time) * 1000
            if getattr(response, "duration_ms", 0.0) > 0:
                duration_ms = response.duration_ms

            # Classification logic
            if response.exit_code == 0:
                # Tests PASSED -> mutant SURVIVED
                mutant.status = "SURVIVED"
                mutant.killing_test = None
            elif response.exit_code in (124, 137) or "timeout" in (response.stderr or "").lower():
                # Execution TIMEOUT -> mutant TIMED OUT
                mutant.status = "TIMEOUT"
                mutant.killing_test = None
            elif response.exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE:
                # Container / sidecar error -> ERROR
                mutant.status = "ERROR"
                mutant.killing_test = None
            else:
                # Tests FAILED -> mutant KILLED
                mutant.status = "KILLED"
                mutant.killing_test = "pytest"

            mutant.execution_time_ms = round(duration_ms, 1)

        except Exception as exc:
            logger.warning("mutant_execution_failed", mutant_id=mutant.mutant_id, error=str(exc))
            mutant.status = "ERROR"
            mutant.execution_time_ms = 0.0

        return mutant

    def execute_campaign(
        self,
        mutants: list[MutantResult],
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
        timeout_seconds: int = 15,
    ) -> MutationSummary:
        """Execute full mutation testing campaign across all generated mutants."""
        start_campaign = time.monotonic()

        for mutant in mutants:
            try:
                self.execute_mutant(
                    mutant=mutant,
                    source_code=source_code,
                    test_code=test_code,
                    sandbox_client=sandbox_client,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                logger.warning("campaign_mutant_skipped", mutant_id=mutant.mutant_id, error=str(exc))
                mutant.status = "ERROR"

        duration_ms = (time.monotonic() - start_campaign) * 1000

        killed_count = sum(1 for m in mutants if m.status == "KILLED")
        survived_count = sum(1 for m in mutants if m.status == "SURVIVED")
        timeout_count = sum(1 for m in mutants if m.status == "TIMEOUT")
        error_count = sum(1 for m in mutants if m.status in ("ERROR", "INCOMPATIBLE"))

        executable_count = killed_count + survived_count + timeout_count
        score_pct = (
            round((killed_count / executable_count) * 100.0, 1)
            if executable_count > 0
            else 0.0
        )

        return MutationSummary(
            total_mutants=len(mutants),
            killed_mutants=killed_count,
            survived_mutants=survived_count,
            timeout_mutants=timeout_count,
            incompatible_mutants=error_count,
            mutation_score_pct=score_pct,
            duration_ms=round(duration_ms, 1),
            mutants=mutants,
        )
