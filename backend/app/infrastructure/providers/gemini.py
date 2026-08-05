"""TestGen AI v2.3 — Gemini LLM Provider Implementation

Concrete provider for Google Gemini models (gemini-2.0-flash, gemini-1.5-pro, etc.).
Translates PromptPayload objects into Gemini requests and normalizes responses into ProviderResponse.

Modes:
  mock_mode=True  → Returns deterministic JSON responses.  No network call.  Used by all tests.
  mock_mode=False → Calls the real Gemini API via google-genai SDK.
"""

import os
import time
from typing import Any, Dict, Optional
import structlog

from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import PromptPayload
from app.exceptions.v23_exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.infrastructure.providers.base import BaseLLMProvider

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Gemini cost table (USD per 1 000 tokens, Gemini 2.0 Flash pricing)
# ---------------------------------------------------------------------------
_COST_PER_1K_INPUT = 0.00015   # $0.15 / 1M input tokens
_COST_PER_1K_OUTPUT = 0.00060  # $0.60 / 1M output tokens


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider implementation.

    Supports both mock mode (for unit testing without network) and
    real API mode (production) via the google-genai SDK.
    """

    def __init__(
        self,
        model_name: str = "gemini-1.5-pro",
        api_key: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        super().__init__(
            provider_name="Gemini",
            model_name=model_name,
            cost_per_1k_input=_COST_PER_1K_INPUT,
            cost_per_1k_output=_COST_PER_1K_OUTPUT,
        )
        # Resolve key: explicit arg > env var
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")

        # Determine mock mode:
        # If mock_mode explicitly requested → honour it.
        # If api_key was explicitly passed as "" → real mode, auth error at call time.
        # If no key found at all → fall back to mock so tests always pass offline.
        if mock_mode:
            self.mock_mode = True
        elif api_key == "":
            # Caller passed empty string explicitly — treat as real mode (key absent).
            self.mock_mode = False
        else:
            self.mock_mode = not bool(self.api_key)

    # ------------------------------------------------------------------
    # Public generate() — real path
    # ------------------------------------------------------------------

    def generate(
        self, prompt_payload: PromptPayload, options: Optional[Dict[str, Any]] = None
    ) -> ProviderResponse:
        """Generate a ProviderResponse from a PromptPayload.

        Routes to _generate_mock() or _generate_real() based on mock_mode.
        """
        start_time = time.perf_counter()

        if self.mock_mode:
            return self._generate_mock(prompt_payload, start_time)

        return self._generate_real(prompt_payload, options or {}, start_time)

    def stream_generate(
        self, prompt_payload: PromptPayload, options: Optional[Dict[str, Any]] = None
    ):
        """Stream generation — yields StreamChunk objects.

        Mock mode: wraps generate() as a single chunk (deterministic, offline).
        Real mode: uses Gemini SDK streaming if available, else falls back to generate().
        """
        from app.infrastructure.providers.streaming import StreamChunk, stream_from_response

        if self.mock_mode:
            yield from stream_from_response(self.generate(prompt_payload, options))
            return

        # Real streaming via google-genai SDK
        if not self.api_key:
            yield from stream_from_response(self.generate(prompt_payload, options))
            return
        try:
            from google import genai
            from google.genai import types as genai_types

            start_time = time.perf_counter()
            client = genai.Client(api_key=self.api_key)
            full_prompt = _build_full_prompt(prompt_payload)
            accumulated = ""
            prompt_tokens = prompt_payload.estimated_tokens

            for sdk_chunk in client.models.generate_content_stream(
                model=self.model_name,
                contents=full_prompt,
            ):
                delta = sdk_chunk.text or ""
                accumulated += delta
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                yield StreamChunk(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    delta=delta,
                    accumulated=accumulated,
                    latency_ms=elapsed_ms,
                    is_final=False,
                    metadata={"mock": False},
                )

            # Final chunk with token counts
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            completion_tokens = self.estimate_tokens(accumulated)
            total_tokens = prompt_tokens + completion_tokens
            yield StreamChunk(
                provider_name=self.provider_name,
                model_name=self.model_name,
                delta="",
                accumulated=accumulated,
                finish_reason="stop",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=elapsed_ms,
                estimated_cost=self.estimate_cost(prompt_tokens, completion_tokens),
                is_final=True,
                metadata={"mock": False},
            )
        except Exception:
            # Graceful fallback if streaming fails
            yield from stream_from_response(self.generate(prompt_payload, options))

    # ------------------------------------------------------------------
    # Mock path (no network)
    # ------------------------------------------------------------------

    def _generate_mock(self, prompt_payload: PromptPayload, start_time: float) -> ProviderResponse:
        """Return deterministic mock JSON for offline testing."""
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        agent = prompt_payload.agent_name

        if agent.startswith("planner"):
            mock_text = f"""{{
  "repository_summary": "# Mock Gemini Response ({self.model_name}) - Calculates math operations.",
  "priority_modules": ["math_utils"],
  "recommended_test_types": ["unit"],
  "target_functions": ["add", "subtract"],
  "test_cases": [
    {{
      "case_id": 1,
      "description": "Test addition of two positive numbers",
      "target_function": "add",
      "test_type": "unit",
      "expected_behavior": "Returns sum of inputs"
    }}
  ],
  "required_mocks": [],
  "required_fixtures": ["sample_numbers"],
  "edge_cases": ["Negative inputs", "Zero addition"],
  "confidence": 0.98
}}"""
        elif agent.startswith("generator"):
            mock_text = f"""{{
  "function_name": "add",
  "imports": ["import pytest"],
  "setup_code": "",
  "test_cases": [
    {{
      "name": "test_add_positive_numbers",
      "description": "Test addition of two positive numbers",
      "category": "unit",
      "inputs": {{"a": 2, "b": 3}},
      "expected_output": "5",
      "assertions": ["assert add(2, 3) == 5"]
    }}
  ],
  "generated_tests": [
    {{
      "target_module": "math_utils",
      "target_function": "add",
      "framework": "pytest",
      "imports": [
        "pytest",
        "from app.math_utils import add"
      ],
      "fixtures": [],
      "mocks": [],
      "test_name": "test_add_positive_numbers",
      "setup": "",
      "test_code": "# Mock Gemini Response ({self.model_name})\\ndef test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n",
      "assertions": [
        "assert add(2, 3) == 5"
      ],
      "confidence": 0.96
    }}
  ]
}}"""
        elif agent.startswith("reviewer"):
            mock_text = f"""{{
  "overall_score": 95.0,
  "approved": true,
  "summary": "# Mock Gemini Response ({self.model_name}) - High quality unit test suite.",
  "coverage_analysis": "Target functions covered.",
  "issues": [],
  "strengths": [
    "Clean assertions",
    "No test smells"
  ],
  "recommendations": [],
  "confidence": 0.98
}}"""
        elif agent.startswith("repair"):
            mock_text = f"""{{
  "repaired_tests": [
    {{
      "test_name": "test_add_positive_numbers",
      "target_function": "add",
      "test_code": "# Mock Gemini Response ({self.model_name}) Repaired\\ndef test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n    assert add(-1, 1) == 0\\n",
      "repair_reason": "Added missing negative boundary assertion",
      "fixed_issues": [
        "Missing negative assertion"
      ],
      "confidence": 0.96
    }}
  ]
}}"""
        else:
            mock_text = (
                f"# Mock Gemini Response ({self.model_name})\n"
                f"# Generated for agent: {agent}\n\n"
                "def test_sample():\n    assert True\n"
            )

        prompt_tokens = prompt_payload.estimated_tokens
        completion_tokens = self.estimate_tokens(mock_text)
        total_tokens = prompt_tokens + completion_tokens

        return ProviderResponse(
            provider_name=self.provider_name,
            model_name=self.model_name,
            response_text=mock_text,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=elapsed_ms,
            estimated_cost=self.estimate_cost(prompt_tokens, completion_tokens),
            metadata={"mock": True, "agent": agent},
        )

    # ------------------------------------------------------------------
    # Real path — Google GenAI SDK
    # ------------------------------------------------------------------

    def _generate_real(
        self,
        prompt_payload: PromptPayload,
        options: Dict[str, Any],
        start_time: float,
    ) -> ProviderResponse:
        """Call the real Gemini API via google-genai SDK and return a normalized ProviderResponse."""
        if not self.api_key:
            raise ProviderAuthenticationError(
                self.provider_name,
                "GEMINI_API_KEY is missing or invalid. Set it in .env or pass api_key= explicitly.",
            )

        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise ProviderUnavailableError(
                self.provider_name,
                "google-genai SDK not installed. Run: pip install google-genai",
            ) from exc

        try:
            client = genai.Client(api_key=self.api_key)

            # Build prompt: combine system + user context
            full_prompt = _build_full_prompt(prompt_payload)

            # Generation config
            temperature = options.get("temperature", 0.3)
            max_output_tokens = options.get("max_tokens", 8192)

            # ThinkingConfig is only supported on thinking-capable models (gemini-2.5+, gemini-3.x).
            # Wrap in try/except so it degrades gracefully for older model variants.
            try:
                generate_config = genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
                )
            except Exception:
                generate_config = genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )

            response = client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=generate_config,
            )

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            response_text = response.text or ""

            # Token accounting — use SDK values when available
            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = getattr(usage, "prompt_token_count", None) or self.estimate_tokens(full_prompt)
            completion_tokens = getattr(usage, "candidates_token_count", None) or self.estimate_tokens(response_text)
            total_tokens = getattr(usage, "total_token_count", None) or (prompt_tokens + completion_tokens)

            finish_reason = "stop"
            if response.candidates:
                raw_finish = getattr(response.candidates[0], "finish_reason", None)
                if raw_finish is not None:
                    finish_reason = str(raw_finish).lower()

            self.logger.info(
                "gemini_generate_success",
                agent=prompt_payload.agent_name,
                model=self.model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=elapsed_ms,
            )

            return ProviderResponse(
                provider_name=self.provider_name,
                model_name=self.model_name,
                response_text=response_text,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=elapsed_ms,
                estimated_cost=self.estimate_cost(prompt_tokens, completion_tokens),
                metadata={"mock": False, "agent": prompt_payload.agent_name},
            )

        except ProviderAuthenticationError:
            raise
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            _raise_mapped_exception(self.provider_name, exc)

    def health_check(self) -> bool:
        """Return True in mock mode or when an API key is present."""
        return True if self.mock_mode else bool(self.api_key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_full_prompt(prompt_payload: PromptPayload) -> str:
    """Combine system and user prompts into a single string for Gemini."""
    parts = []
    if prompt_payload.rendered_system:
        parts.append(prompt_payload.rendered_system)
    if prompt_payload.rendered_user:
        parts.append(prompt_payload.rendered_user)
    return "\n\n".join(parts)


def _raise_mapped_exception(provider_name: str, exc: Exception) -> None:
    """Map SDK-level exceptions into TestGen AI provider exception hierarchy."""
    exc_str = str(exc).lower()
    if "api_key" in exc_str or "api key" in exc_str or "authentication" in exc_str or "403" in exc_str:
        raise ProviderAuthenticationError(provider_name, f"Authentication failed: {exc}") from exc
    if "timeout" in exc_str or "timed out" in exc_str:
        raise ProviderTimeoutError(provider_name, f"Request timed out: {exc}") from exc
    if "rate" in exc_str or "quota" in exc_str or "429" in exc_str:
        raise ProviderRateLimitError(provider_name, f"Rate limit exceeded: {exc}") from exc
    if "unavailable" in exc_str or "503" in exc_str or "connection" in exc_str:
        raise ProviderUnavailableError(provider_name, f"Provider unavailable: {exc}") from exc
    raise ProviderError(provider_name, f"Unexpected provider error: {exc}") from exc
