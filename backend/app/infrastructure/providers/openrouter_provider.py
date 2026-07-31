"""TestGen AI v2.3 — OpenRouter LLM Provider Implementation

Concrete provider for OpenRouter-hosted models (deepseek/deepseek-r1, etc.).
OpenRouter exposes an OpenAI-compatible Chat Completions API, so this
implementation reuses the openai SDK pointed at https://openrouter.ai/api/v1.

Modes:
  mock_mode=True  → Deterministic JSON responses. No network. Used by all tests.
  mock_mode=False → Real OpenRouter API via openai SDK with custom base_url.
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
# OpenRouter configuration
# ---------------------------------------------------------------------------
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "deepseek/deepseek-r1"

# Cost per 1K tokens — deepseek-r1 pricing via OpenRouter
# https://openrouter.ai/deepseek/deepseek-r1
_COST_PER_1K_INPUT = 0.00055   # $0.55 / 1M input tokens
_COST_PER_1K_OUTPUT = 0.00219  # $2.19 / 1M output tokens


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider implementation.

    Uses the OpenAI-compatible API exposed by OpenRouter at:
      https://openrouter.ai/api/v1

    Supports both mock mode (offline testing) and real API mode.
    Any model listed on openrouter.ai can be used via OPENROUTER_MODEL.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        api_key: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        super().__init__(
            provider_name="OpenRouter",
            model_name=model_name,
            cost_per_1k_input=_COST_PER_1K_INPUT,
            cost_per_1k_output=_COST_PER_1K_OUTPUT,
        )
        self.api_key = api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY", "")
        self.mock_mode = mock_mode or not bool(self.api_key)

    # ------------------------------------------------------------------
    # Public generate()
    # ------------------------------------------------------------------

    def generate(
        self, prompt_payload: PromptPayload, options: Optional[Dict[str, Any]] = None
    ) -> ProviderResponse:
        """Generate a ProviderResponse from a PromptPayload."""
        start_time = time.perf_counter()

        if self.mock_mode:
            return self._generate_mock(prompt_payload, start_time)

        return self._generate_real(prompt_payload, options or {}, start_time)

    def stream_generate(
        self, prompt_payload: PromptPayload, options: Optional[Dict[str, Any]] = None
    ):
        """Stream generation via OpenRouter OpenAI-compatible streaming API."""
        from app.infrastructure.providers.streaming import StreamChunk, stream_from_response

        if self.mock_mode:
            yield from stream_from_response(self.generate(prompt_payload, options))
            return

        if not self.api_key:
            yield from stream_from_response(self.generate(prompt_payload, options))
            return

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.api_key,
                base_url=_OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://github.com/TestGenAI",
                    "X-Title": "TestGen AI",
                },
            )
            messages = _build_messages(prompt_payload)
            temperature = (options or {}).get("temperature", 0.3)
            max_tokens = (options or {}).get("max_tokens", 4096)
            start_time = time.perf_counter()
            accumulated = ""
            prompt_tokens = prompt_payload.estimated_tokens

            with client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            ) as stream:
                for sdk_chunk in stream:
                    delta = ""
                    if sdk_chunk.choices and sdk_chunk.choices[0].delta.content:
                        delta = sdk_chunk.choices[0].delta.content
                    accumulated += delta
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    finish = None
                    if sdk_chunk.choices and sdk_chunk.choices[0].finish_reason:
                        finish = sdk_chunk.choices[0].finish_reason
                    yield StreamChunk(
                        provider_name=self.provider_name,
                        model_name=self.model_name,
                        delta=delta,
                        accumulated=accumulated,
                        finish_reason=finish,
                        latency_ms=elapsed_ms,
                        is_final=bool(finish),
                        metadata={"mock": False, "base_url": _OPENROUTER_BASE_URL},
                    )

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            completion_tokens = self.estimate_tokens(accumulated)
            yield StreamChunk(
                provider_name=self.provider_name,
                model_name=self.model_name,
                delta="",
                accumulated=accumulated,
                finish_reason="stop",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=elapsed_ms,
                estimated_cost=self.estimate_cost(prompt_tokens, completion_tokens),
                is_final=True,
                metadata={"mock": False, "base_url": _OPENROUTER_BASE_URL},
            )
        except Exception:
            yield from stream_from_response(self.generate(prompt_payload, options))

    # ------------------------------------------------------------------
    # Mock path (no network)
    # ------------------------------------------------------------------

    def _generate_mock(self, prompt_payload: PromptPayload, start_time: float) -> ProviderResponse:
        """Return deterministic mock JSON for offline testing."""
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        agent = prompt_payload.agent_name

        if agent.startswith("planner"):
            mock_text = """{
  "repository_summary": "Calculates math operations.",
  "priority_modules": ["math_utils"],
  "recommended_test_types": ["unit"],
  "target_functions": ["add", "subtract"],
  "test_cases": [
    {
      "case_id": 1,
      "description": "Test addition of two positive numbers",
      "target_function": "add",
      "test_type": "unit",
      "expected_behavior": "Returns sum of inputs"
    }
  ],
  "required_mocks": [],
  "required_fixtures": ["sample_numbers"],
  "edge_cases": ["Negative inputs", "Zero addition"],
  "confidence": 0.98
}"""
        elif agent.startswith("generator"):
            mock_text = f"""{{
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
      "test_code": "# Mock OpenRouter Response ({self.model_name})\\ndef test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n",
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
  "summary": "# Mock OpenRouter Response ({self.model_name}) - High quality unit test suite.",
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
      "test_code": "# Mock OpenRouter Response ({self.model_name}) Repaired\\ndef test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n    assert add(-1, 1) == 0\\n",
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
                f"# Mock OpenRouter Response ({self.model_name})\n"
                f"# Agent: {agent}\n\n"
                "def test_openrouter_sample():\n    assert True\n"
            )

        prompt_tokens = prompt_payload.estimated_tokens
        completion_tokens = self.estimate_tokens(mock_text)

        return ProviderResponse(
            provider_name=self.provider_name,
            model_name=self.model_name,
            response_text=mock_text,
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=elapsed_ms,
            estimated_cost=self.estimate_cost(prompt_tokens, completion_tokens),
            metadata={"mock": True, "agent": agent},
        )

    # ------------------------------------------------------------------
    # Real path — OpenAI SDK pointed at OpenRouter
    # ------------------------------------------------------------------

    def _generate_real(
        self,
        prompt_payload: PromptPayload,
        options: Dict[str, Any],
        start_time: float,
    ) -> ProviderResponse:
        """Call OpenRouter via the OpenAI-compatible API."""
        if not self.api_key:
            raise ProviderAuthenticationError(
                self.provider_name,
                "OPENROUTER_API_KEY is missing or invalid. Set it in .env or pass api_key= explicitly.",
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailableError(
                self.provider_name,
                "openai SDK not installed. Run: pip install openai>=1.40.0",
            ) from exc

        try:
            # OpenRouter is OpenAI-compatible — just override the base_url
            client = OpenAI(
                api_key=self.api_key,
                base_url=_OPENROUTER_BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://github.com/TestGenAI",
                    "X-Title": "TestGen AI",
                },
            )

            messages = _build_messages(prompt_payload)
            temperature = options.get("temperature", 0.3)
            max_tokens = options.get("max_tokens", 4096)

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response_text = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or "stop"

            # Token accounting from SDK
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else self.estimate_tokens(str(messages))
            completion_tokens = usage.completion_tokens if usage else self.estimate_tokens(response_text)
            total_tokens = usage.total_tokens if usage else (prompt_tokens + completion_tokens)

            self.logger.info(
                "openrouter_generate_success",
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
                metadata={
                    "mock": False,
                    "agent": prompt_payload.agent_name,
                    "base_url": _OPENROUTER_BASE_URL,
                },
            )

        except ProviderAuthenticationError:
            raise
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            _raise_mapped_exception(self.provider_name, exc)

    def health_check(self) -> bool:
        return True if self.mock_mode else bool(self.api_key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_messages(prompt_payload: PromptPayload) -> list:
    """Build chat messages list from PromptPayload."""
    messages = []
    if prompt_payload.rendered_system:
        messages.append({"role": "system", "content": prompt_payload.rendered_system})
    if prompt_payload.rendered_user:
        messages.append({"role": "user", "content": prompt_payload.rendered_user})
    return messages


def _raise_mapped_exception(provider_name: str, exc: Exception) -> None:
    """Map OpenAI/OpenRouter SDK exceptions into the provider exception hierarchy."""
    exc_type = type(exc).__name__.lower()
    exc_str = str(exc).lower()
    if "authenticationerror" in exc_type or "api_key" in exc_str or "401" in exc_str:
        raise ProviderAuthenticationError(provider_name, f"Authentication failed: {exc}") from exc
    if "timeout" in exc_type or "timeout" in exc_str:
        raise ProviderTimeoutError(provider_name, f"Request timed out: {exc}") from exc
    if "ratelimit" in exc_type or "rate_limit" in exc_str or "429" in exc_str:
        raise ProviderRateLimitError(provider_name, f"Rate limit exceeded: {exc}") from exc
    if "apierror" in exc_type or "503" in exc_str or "connection" in exc_str:
        raise ProviderUnavailableError(provider_name, f"Provider unavailable: {exc}") from exc
    raise ProviderError(provider_name, f"Unexpected provider error: {exc}") from exc
