"""Mutation Runner Orchestrator Service for TestGen AI v2.2.

Pure orchestrator that traverses source code AST, dispatches candidate nodes to
registered MutationOperator strategies, generates in-memory mutated code variants,
deduplicates mutants, and returns structured MutationSummary reports.
Stateless, deterministic, side-effect free, and never executes code or modifies files.
"""

import ast
import copy
import hashlib
from typing import Any
import structlog

from app.domain.mutation import (
    MutantResult,
    MutationProvider,
    MutationSummary,
)
from app.services.mutation_operators import (
    DEFAULT_MUTATION_OPERATORS,
    MutationOperator,
)

logger = structlog.get_logger(__name__)


class MutationRunner(MutationProvider):
    """Orchestrates in-memory AST code mutation generation using pluggable MutationOperators."""

    __test__ = False

    def __init__(
        self,
        provider: Any = None,
        operators: list[MutationOperator] | None = None,
        executor: Any = None,
    ) -> None:
        """Initialize MutationRunner with registered operators and optional executor."""
        self.operators: list[MutationOperator] = (
            operators if operators is not None else DEFAULT_MUTATION_OPERATORS
        )
        self.executor = executor

    @property
    def name(self) -> str:
        """Return unique provider identifier."""
        return "ast"

    def generate_mutants(self, source_code: str) -> list[MutantResult]:
        """Generate deduplicated list of MutantResult objects from source code AST."""
        if not source_code or not source_code.strip():
            return []

        try:
            tree = ast.parse(source_code)
        except Exception as exc:
            logger.warning("mutation_runner_ast_parse_error", error=str(exc))
            return []

        mutants: list[MutantResult] = []
        seen_signatures: set[str] = set()

        for node in ast.walk(tree):
            if not hasattr(node, "lineno"):
                continue

            lineno = getattr(node, "lineno", 0)

            for op in self.operators:
                if isinstance(node, op.supported_node_types):
                    mutated_variants = op.mutate(node)
                    for mutated_subnode, description in mutated_variants:
                        mutated_tree = copy.deepcopy(tree)
                        replaced = self._replace_ast_node(
                            mutated_tree, target_node=node, replacement=mutated_subnode
                        )
                        if not replaced:
                            continue

                        try:
                            mutated_code = ast.unparse(mutated_tree)
                        except Exception:
                            continue

                        mutated_line = self._extract_line(mutated_code, lineno)
                        signature = f"{lineno}:{mutated_line}:{op.category}"

                        if signature in seen_signatures:
                            continue
                        seen_signatures.add(signature)

                        hash_input = f"{op.category}:{lineno}:{mutated_line}".encode("utf-8")
                        short_hash = hashlib.md5(hash_input).hexdigest()[:8].upper()
                        mutant_id = f"MUT_{op.category}_{lineno}_{short_hash}"

                        mutants.append(
                            MutantResult(
                                mutant_id=mutant_id,
                                category=op.category,
                                description=description,
                                original_line=lineno,
                                mutated_line_content=mutated_line,
                                status="UNTESTED",
                                killing_test=None,
                                execution_time_ms=0.0,
                            )
                        )

        return mutants

    def execute_mutation_pass(
        self,
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
    ) -> MutationSummary:
        """Generate mutants from source code and execute mutation campaign if sandbox_client is provided."""
        mutants = self.generate_mutants(source_code)
        if not mutants:
            return MutationSummary(total_mutants=0, mutants=[])

        if sandbox_client is not None or self.executor is not None:
            from app.services.mutation_execution.docker_executor import DockerMutationExecutor
            exec_strategy = self.executor or DockerMutationExecutor()
            return exec_strategy.execute_campaign(
                mutants=mutants,
                source_code=source_code,
                test_code=test_code,
                sandbox_client=sandbox_client,
            )

        return MutationSummary(
            total_mutants=len(mutants),
            killed_mutants=0,
            survived_mutants=0,
            timeout_mutants=0,
            incompatible_mutants=0,
            mutation_score_pct=0.0,
            duration_ms=0.0,
            mutants=mutants,
        )

    def run_mutation_analysis(
        self,
        source_code: str,
        test_code: str,
        sandbox_client: Any = None,
    ) -> MutationSummary:
        """Alias for execute_mutation_pass() providing interface compatibility."""
        return self.execute_mutation_pass(
            source_code=source_code,
            test_code=test_code,
            sandbox_client=sandbox_client,
        )

    def _replace_ast_node(
        self,
        tree: ast.AST,
        target_node: ast.AST,
        replacement: ast.AST,
    ) -> bool:
        """Locate target_node in tree by lineno, col_offset, and type, and replace with replacement."""
        target_lineno = getattr(target_node, "lineno", None)
        target_col = getattr(target_node, "col_offset", None)
        target_type = type(target_node)

        class NodeReplacer(ast.NodeTransformer):
            def __init__(self) -> None:
                super().__init__()
                self.replaced = False

            def visit(self, node: ast.AST) -> ast.AST:
                if (
                    not self.replaced
                    and type(node) is target_type
                    and getattr(node, "lineno", None) == target_lineno
                    and getattr(node, "col_offset", None) == target_col
                ):
                    self.replaced = True
                    return replacement
                return self.generic_visit(node)

        replacer = NodeReplacer()
        replacer.visit(tree)
        return replacer.replaced

    def _extract_line(self, code: str, line_no: int) -> str:
        """Extract a specific 1-indexed line from source code string."""
        lines = code.splitlines()
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1].strip()
        return code.splitlines()[0].strip() if lines else ""
