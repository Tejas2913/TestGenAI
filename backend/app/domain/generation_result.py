"""End-to-end result of the test generation pipeline."""

from typing import Any

from pydantic import BaseModel, Field

from app.domain.test_suite import TestSuite


class GenerationResult(BaseModel):
    """Final output combining all pipeline artifacts.

    Phase 3 addition: sandbox_result carries the SandboxExecuteResponse
    when sandbox execution is enabled. None when sandbox_client is not
    injected (V1 path) or when ENABLE_SANDBOX=False.
    """

    test_suite: TestSuite = Field(description="Validated test suite")
    raw_response: str = Field(description="Raw LLM response text")
    parsed_json: dict[str, Any] = Field(description="Parsed JSON before model conversion")
    generated_code: str = Field(description="Rendered pytest source code")
    validation_warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings from validators",
    )
    # Phase 3: sandbox execution result — None when sandbox is disabled or
    # unavailable. Populated by GenerationService when sandbox_client is injected.
    sandbox_result: Any | None = Field(
        default=None,
        description="SandboxExecuteResponse or None if sandbox not executed",
    )
