"""Business service orchestrating the test generation pipeline.

This is the single point of orchestration between:
- AI Engine (InputAnalyser, PromptBuilder, ResponseParser, Validators, CodeGenerator)
- LLM Provider (GeminiProvider)
- Persistence (GenerationRepository)
- Sandbox (SandboxClient) — Phase 3 addition
- Cache (CacheManager) — Phase 4 addition
- ContextProvider  — Phase 4 addition

Phase 4.5 hardening:
- Generation ID correlation through all log entries
- Pipeline execution timing
- Prompt version tracking
- Token usage persistence
- Input size validation
- Improved error categorization

Phase 3 additions:
- Optional SandboxClient injection (sandbox_client=None → skip sandbox; V1 unaffected)
- SandboxExecuteResponse persisted in GenerationResult for job engine use
- Checkpoint-aware _run_pipeline with resume_from parameter

Phase 4 additions:
- Optional ContextProvider injection (context_provider=None → DefaultContextProvider used)
- Optional CacheManager injection (cache_manager=None → cache disabled for this call)
- Two-tier cache lookup (L1→L2) before running the LLM pipeline
- Cache write after successful pipeline (L1 + L2 when enabled)
- Context string from ContextProvider appended to specification before prompt building
"""

import json
import time

import structlog  # pyrefly: ignore [missing-import]

from app.ai.code_generator import CodeGenerator
from app.ai.input_analyser import InputAnalyser
from app.ai.prompt_builder import PromptBuilder
from app.ai.providers.base import LLMProvider
from app.ai.response_parser import ResponseParser
from app.ai.validators import (
    BusinessRuleValidator,
    JSONSchemaValidator,
    SemanticValidator,
)
from app.core.config import settings
from app.domain.generation_result import GenerationResult
from app.exceptions import (
    AppException,
    InputTooLargeException,
    LLMException,
    ValidationException,
)
from app.models.generation import Generation
from app.repositories.generation_repository import GenerationRepository

logger = structlog.get_logger()


class GenerationService:
    """Orchestrates the full test generation pipeline.

    V1 lifecycle (sandbox_client=None):
        1. Validate input sizes
        2. Create a DB record (status=pending)
        3. Update to processing
        4. Run pipeline: analyse -> prompt -> LLM -> parse -> validate -> generate
        5. Persist results (status=completed) or error (status=failed)
        6. Return the Generation record

    V2 addition (sandbox_client provided):
        Step 4 gains an additional stage after code generation:
        -> SandboxClient.execute(generated_code)
        Result is attached to GenerationResult.sandbox_result.
    """

    def __init__(
        self,
        repository: GenerationRepository,
        llm_provider: LLMProvider,
        sandbox_client=None,       # SandboxClient | None — Phase 3
        context_provider=None,     # ContextProvider | None — Phase 4
        cache_manager=None,        # CacheManager | None — Phase 4
    ) -> None:
        self._repository = repository
        self._llm_provider = llm_provider
        self._sandbox_client = sandbox_client

        # Phase 4: ContextProvider (default = no additional context)
        if context_provider is None:
            from app.context.provider import DefaultContextProvider
            self._context_provider = DefaultContextProvider()
        else:
            self._context_provider = context_provider

        # Phase 4: CacheManager (None = caching disabled for this instance)
        self._cache_manager = cache_manager

        # AI Engine components (stateless, reusable)
        self._analyser = InputAnalyser()
        self._prompt_builder = PromptBuilder()
        self._response_parser = ResponseParser()
        self._schema_validator = JSONSchemaValidator()
        self._semantic_validator = SemanticValidator()
        self._business_validator = BusinessRuleValidator()
        self._code_generator = CodeGenerator()

    def generate(
        self,
        source_code: str,
        specification: str | None = None,
        language: str = "python",
        framework: str = "pytest",
        resume_from_checkpoint: str | None = None,
        checkpoint_payload: str | None = None,
    ) -> Generation:
        """Execute the full test generation pipeline.

        Args:
            source_code:             Python source to generate tests for.
            specification:           Optional plain-English constraints.
            language:                Source language tag (unused by engine, stored).
            framework:               Test framework (passed to CodeGenerator).
            resume_from_checkpoint:  Last checkpoint name — pipeline skips
                                     completed stages on crash recovery.
            checkpoint_payload:      Serialised JSON from the last checkpoint
                                     (e.g. raw LLM response at LLM_RESPONDED).

        Returns:
            The persisted Generation ORM record with results.
        """
        # Step 0: Validate input sizes
        self._validate_input_sizes(source_code, specification)

        # ----------------------------------------------------------------
        # Phase 4: Two-tier cache lookup (L1 → L2)
        # On cache hit, skip the LLM pipeline entirely.
        # ----------------------------------------------------------------
        from app.cache.keys import compute_cache_key, compute_prompt_hash

        cache_key = compute_cache_key(
            source_code=source_code,
            specification=specification,
            language=language,
            framework=framework,
            prompt_version=settings.PROMPT_VERSION,
        )
        prompt_hash = compute_prompt_hash(settings.PROMPT_VERSION)

        if self._cache_manager is not None:
            cached = self._cache_manager.get(cache_key)
            if cached is not None:
                # Cache hit — create a Generation record with cached artifacts
                # and return without touching the LLM.
                record = self._repository.create({
                    "source_code": source_code,
                    "specification": specification,
                    "language": language,
                    "framework": framework,
                    "status": "completed",
                    "prompt_version": settings.PROMPT_VERSION,
                    "architecture_version": settings.ARCHITECTURE_VERSION,
                    "generated_tests_json": cached.get("generated_tests_json", ""),
                    "generated_tests_code": cached.get("generated_tests_code", ""),
                })
                logger.info(
                    "generation_cache_hit",
                    generation_id=record.id,
                    cache_key=cache_key[:8],
                    prompt_version=settings.PROMPT_VERSION,
                )
                return record

        # Step 1: Create pending record
        record = self._repository.create({
            "source_code": source_code,
            "specification": specification,
            "language": language,
            "framework": framework,
            "status": "pending",
            "prompt_version": settings.PROMPT_VERSION,
            "architecture_version": settings.ARCHITECTURE_VERSION,
        })
        generation_id = record.id

        log = logger.bind(
            generation_id=generation_id,
            prompt_version=settings.PROMPT_VERSION,
        )
        log.info("generation_created")

        # Step 2: Update to processing
        self._repository.update(generation_id, {"status": "processing"})

        pipeline_start = time.monotonic()

        try:
            result = self._run_pipeline(
                source_code=source_code,
                specification=specification,
                framework=framework,
                log=log,
                resume_from_checkpoint=resume_from_checkpoint,
                checkpoint_payload=checkpoint_payload,
            )

            pipeline_duration_ms = (time.monotonic() - pipeline_start) * 1000

            # Extract token usage from provider if available
            usage = getattr(self._llm_provider, "last_usage", None) or {}

            # Step 4: Persist successful results
            update_data = {
                "status": "completed",
                "generated_tests_json": json.dumps(
                    result.parsed_json, indent=2
                ),
                "generated_tests_code": result.generated_code,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "duration_ms": round(pipeline_duration_ms, 2),
                # Phase 3: persist sandbox result when available
                "sandbox_exit_code": getattr(result.sandbox_result, "exit_code", None),
                "sandbox_stdout":    getattr(result.sandbox_result, "stdout", None),
                "sandbox_stderr":    getattr(result.sandbox_result, "stderr", None),
                "sandbox_duration_ms": getattr(result.sandbox_result, "duration_ms", None),
                # Coverage metrics
                "coverage_line_pct": getattr(result.sandbox_result, "coverage_line_pct", None),
                "coverage_branch_pct": getattr(result.sandbox_result, "coverage_branch_pct", None),
                "coverage_total_statements": getattr(result.sandbox_result, "coverage_total_statements", None),
                "coverage_covered_statements": getattr(result.sandbox_result, "coverage_covered_statements", None),
                "coverage_missing_statements": getattr(result.sandbox_result, "coverage_missing_statements", None),
            }
            self._repository.update(generation_id, update_data)

            # ----------------------------------------------------------------
            # Phase 4: Write successful result to cache
            # ----------------------------------------------------------------
            if self._cache_manager is not None:
                cache_value = {
                    "generated_tests_json": json.dumps(result.parsed_json, indent=2),
                    "generated_tests_code": result.generated_code,
                    "validation_warnings": result.validation_warnings,
                    "raw_response": result.raw_response,
                    "prompt_hash": prompt_hash,
                    "from_cache": False,
                }
                self._cache_manager.set(
                    cache_key=cache_key,
                    prompt_hash=prompt_hash,
                    value=cache_value,
                    language=language,
                    framework=framework,
                )

            log.info(
                "generation_completed",
                test_count=len(result.test_suite.test_cases),
                validation_warnings=len(result.validation_warnings),
                duration_ms=round(pipeline_duration_ms, 2),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                retry_count=usage.get("retry_count", 0),
                sandbox_exit_code=getattr(
                    result.sandbox_result, "exit_code", None
                ),
            )

        except (InputTooLargeException, ValidationException) as exc:
            pipeline_duration_ms = (time.monotonic() - pipeline_start) * 1000
            self._repository.update(generation_id, {
                "status": "failed",
                "error_message": exc.detail,
                "duration_ms": round(pipeline_duration_ms, 2),
            })
            log.warning(
                "generation_validation_failed",
                error=exc.detail,
                error_code=exc.error_code,
                duration_ms=round(pipeline_duration_ms, 2),
            )

        except LLMException as exc:
            pipeline_duration_ms = (time.monotonic() - pipeline_start) * 1000
            usage = getattr(self._llm_provider, "last_usage", None) or {}
            self._repository.update(generation_id, {
                "status": "failed",
                "error_message": exc.detail,
                "duration_ms": round(pipeline_duration_ms, 2),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            })
            log.warning(
                "generation_llm_failed",
                error=exc.detail,
                error_code=exc.error_code,
                duration_ms=round(pipeline_duration_ms, 2),
                retry_count=usage.get("retry_count", 0),
            )

        except AppException as exc:
            pipeline_duration_ms = (time.monotonic() - pipeline_start) * 1000
            self._repository.update(generation_id, {
                "status": "failed",
                "error_message": exc.detail,
                "duration_ms": round(pipeline_duration_ms, 2),
            })
            log.warning(
                "generation_app_failed",
                error=exc.detail,
                error_code=exc.error_code,
                duration_ms=round(pipeline_duration_ms, 2),
            )

        except Exception as exc:
            pipeline_duration_ms = (time.monotonic() - pipeline_start) * 1000
            self._repository.update(generation_id, {
                "status": "failed",
                "error_message": str(exc),
                "duration_ms": round(pipeline_duration_ms, 2),
            })
            log.error(
                "generation_unexpected_error",
                error=str(exc),
                duration_ms=round(pipeline_duration_ms, 2),
                exc_info=True,
            )

        # Return the final record regardless of outcome
        return self._repository.get_by_id(generation_id)

    def get_by_id(self, generation_id: str) -> Generation | None:
        """Retrieve a generation record by ID."""
        return self._repository.get_by_id(generation_id)

    def get_history(
        self, page: int = 1, size: int = 20
    ) -> tuple[list[Generation], int]:
        """Retrieve paginated generation history."""
        offset = (page - 1) * size
        return self._repository.get_all(offset=offset, limit=size)

    def _validate_input_sizes(
        self, source_code: str, specification: str | None
    ) -> None:
        """Enforce configurable input size limits."""
        if len(source_code) > settings.MAX_SOURCE_CODE_SIZE:
            raise InputTooLargeException(
                detail=(
                    f"Source code exceeds maximum size: "
                    f"{len(source_code)} bytes "
                    f"(limit: {settings.MAX_SOURCE_CODE_SIZE} bytes)"
                )
            )
        if specification and len(specification) > settings.MAX_SPECIFICATION_SIZE:
            raise InputTooLargeException(
                detail=(
                    f"Specification exceeds maximum size: "
                    f"{len(specification)} bytes "
                    f"(limit: {settings.MAX_SPECIFICATION_SIZE} bytes)"
                )
            )

    def _run_pipeline(
        self,
        source_code: str,
        specification: str | None,
        framework: str,
        log: structlog.BoundLogger,
        resume_from_checkpoint: str | None = None,
        checkpoint_payload: str | None = None,
    ) -> GenerationResult:
        """Execute the AI pipeline stages. Raises on failure.

        When resume_from_checkpoint is provided, stages completed before
        the checkpoint are skipped. The checkpoint_payload carries the
        serialised output of the last stage so we can deserialise it and
        continue from there.

        Checkpoint order:
          ANALYZED → PROMPTED → LLM_RESPONDED → PARSED → SANDBOX_TESTED
        """
        from app.models.job import (
            CHECKPOINT_ANALYZED,
            CHECKPOINT_LLM_RESPONDED,
            CHECKPOINT_PARSED,
            CHECKPOINT_PROMPTED,
            CHECKPOINT_SANDBOX_TESTED,
        )

        _STAGE_ORDER = [
            CHECKPOINT_ANALYZED,
            CHECKPOINT_PROMPTED,
            CHECKPOINT_LLM_RESPONDED,
            CHECKPOINT_PARSED,
            CHECKPOINT_SANDBOX_TESTED,
        ]

        def _already_done(stage: str) -> bool:
            """Return True if the stage was completed before the crash."""
            if resume_from_checkpoint is None:
                return False
            if stage not in _STAGE_ORDER or resume_from_checkpoint not in _STAGE_ORDER:
                return False
            return (
                _STAGE_ORDER.index(stage)
                <= _STAGE_ORDER.index(resume_from_checkpoint)
            )

        # ----------------------------------------------------------------
        # Stage 1: Analyse input
        # ----------------------------------------------------------------
        if _already_done(CHECKPOINT_ANALYZED) and checkpoint_payload:
            # Deserialise the analysed metadata from checkpoint payload
            saved = json.loads(checkpoint_payload)
            # We cannot reconstruct the InputMetadata object cheaply from JSON
            # so we re-analyse (fast, local, no LLM call).
            metadata = self._analyser.analyse(source_code)
        else:
            metadata = self._analyser.analyse(source_code)
        log.debug("pipeline_stage", stage="input_analyser",
                  function=metadata.function_name)

        # ----------------------------------------------------------------
        # Stage 2: Build prompts
        # ContextProvider injects additional context (Phase 4).
        # DefaultContextProvider returns "" — no change to V1 behaviour.
        # ----------------------------------------------------------------
        additional_context = self._context_provider.get_context(source_code, specification)
        effective_specification = specification
        if additional_context:
            effective_specification = (
                f"{specification or ''}".strip()
                + f"\n\nAdditional Context:\n{additional_context}"
            ).strip()

        payload = self._prompt_builder.build(metadata, effective_specification)
        log.debug("pipeline_stage", stage="prompt_builder",
                  context_provider=self._context_provider.provider_name,
                  context_injected=bool(additional_context))

        # ----------------------------------------------------------------
        # Stage 3: Call LLM (skip if we have a cached response)
        # ----------------------------------------------------------------
        if _already_done(CHECKPOINT_LLM_RESPONDED) and checkpoint_payload:
            saved = json.loads(checkpoint_payload)
            raw_response = saved.get("raw_response", "")
            log.info("pipeline_stage_resumed", stage="llm_provider",
                     from_checkpoint=CHECKPOINT_LLM_RESPONDED)
        else:
            raw_response = self._llm_provider.generate(payload)
        log.debug("pipeline_stage", stage="llm_provider",
                  response_len=len(raw_response))

        # ----------------------------------------------------------------
        # Stage 4: Parse response into typed TestSuite
        # ----------------------------------------------------------------
        test_suite = self._response_parser.parse(raw_response)
        log.debug("pipeline_stage", stage="response_parser",
                  test_count=len(test_suite.test_cases))

        # ----------------------------------------------------------------
        # Stage 5: Validate
        # ----------------------------------------------------------------
        validation_warnings: list[str] = []
        validation_warnings.extend(self._schema_validator.validate(test_suite))
        validation_warnings.extend(self._semantic_validator.validate(test_suite))
        validation_warnings.extend(self._business_validator.validate(test_suite))

        if validation_warnings:
            log.info("validation_warnings", count=len(validation_warnings),
                     warnings=validation_warnings[:10])

        # ----------------------------------------------------------------
        # Stage 6: Generate code
        # ----------------------------------------------------------------
        generated_code = self._code_generator.generate(test_suite, framework)
        log.debug("pipeline_stage", stage="code_generator",
                  code_len=len(generated_code))

        # ----------------------------------------------------------------
        # Stage 7: Sandbox execution (Phase 3, optional)
        # ----------------------------------------------------------------
        sandbox_result = None
        if self._sandbox_client is not None and settings.ENABLE_SANDBOX:
            from app.sandbox.schemas import SandboxExecuteRequest
            req = SandboxExecuteRequest(
                code=generated_code,
                source_code=source_code,
                framework=framework,
                timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
            )
            sandbox_result = self._sandbox_client.execute(req)
            log.info(
                "pipeline_stage",
                stage="sandbox",
                exit_code=sandbox_result.exit_code,
                duration_ms=sandbox_result.duration_ms,
            )

        # Build parsed JSON for storage
        parsed_json = {
            "function_name": test_suite.function_name,
            "test_cases": [tc.model_dump() for tc in test_suite.test_cases],
            "imports": test_suite.imports,
            "setup_code": test_suite.setup_code,
        }

        return GenerationResult(
            test_suite=test_suite,
            raw_response=raw_response,
            parsed_json=parsed_json,
            generated_code=generated_code,
            validation_warnings=validation_warnings,
            sandbox_result=sandbox_result,
        )
