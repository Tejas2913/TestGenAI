"""TestGen AI v2.3 — OpenAI LLM Provider Implementation

Concrete provider for OpenAI models (gpt-4o, gpt-4o-mini, gpt-4-turbo).
Translates PromptPayload objects into OpenAI requests and normalizes responses into ProviderResponse.

Modes:
  mock_mode=True  → Returns deterministic JSON responses.  No network call.  Used by all tests.
  mock_mode=False → Calls the real OpenAI Chat Completions API via openai SDK.
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
# OpenAI cost table (USD per 1 000 tokens, gpt-4o pricing)
# ---------------------------------------------------------------------------
_COST_PER_1K_INPUT = 0.0025    # $2.50 / 1M input tokens
_COST_PER_1K_OUTPUT = 0.010    # $10.00 / 1M output tokens


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider implementation.

    Supports both mock mode (for unit testing without network) and
    real API mode (production) via the openai SDK.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        mock_mode: bool = False,
    ) -> None:
        super().__init__(
            provider_name="OpenAI",
            model_name=model_name,
            cost_per_1k_input=_COST_PER_1K_INPUT,
            cost_per_1k_output=_COST_PER_1K_OUTPUT,
        )
        # Resolve key: explicit arg > env var
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY", "")
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
        """Stream generation yielding StreamChunk objects via OpenAI streaming API."""
        from app.infrastructure.providers.streaming import StreamChunk, stream_from_response

        if self.mock_mode:
            yield from stream_from_response(self.generate(prompt_payload, options))
            return

        if not self.api_key:
            yield from stream_from_response(self.generate(prompt_payload, options))
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
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
                        metadata={"mock": False},
                    )

            # Ensure a final chunk is emitted
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
                metadata={"mock": False},
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
      "test_code": "# Mock OpenAI Response ({self.model_name})\\ndef test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n",
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
  "summary": "# Mock OpenAI Response ({self.model_name}) - High quality unit test suite.",
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
      "test_code": "# Mock OpenAI Response ({self.model_name}) Repaired\\ndef test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n    assert add(-1, 1) == 0\\n",
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
                f"# Mock OpenAI Response ({self.model_name})\n"
                f"# Agent: {agent}\n\n"
                "def test_openai_sample():\n    assert 1 + 1 == 2\n"
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
    # Real path — OpenAI SDK
    # ------------------------------------------------------------------

    def _generate_real(
        self,
        prompt_payload: PromptPayload,
        options: Dict[str, Any],
        start_time: float,
    ) -> ProviderResponse:
        """Call the real OpenAI Chat Completions API."""
        if not self.api_key:
            raise ProviderAuthenticationError(
                self.provider_name,
                "OPENAI_API_KEY is missing. Set it in .env or pass api_key= explicitly.",
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailableError(
                self.provider_name,
                "openai SDK not installed. Run: pip install openai>=1.40.0",
            ) from exc

        try:
            client = OpenAI(api_key=self.api_key)

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
                "openai_generate_success",
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
        return True if self.mock_mode else bool(self.api_key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_messages(prompt_payload: PromptPayload) -> list:
    """Build OpenAI-style messages list from PromptPayload."""
    messages = []
    if prompt_payload.rendered_system:
        messages.append({"role": "system", "content": prompt_payload.rendered_system})
    if prompt_payload.rendered_user:
        messages.append({"role": "user", "content": prompt_payload.rendered_user})
    return messages


def _raise_mapped_exception(provider_name: str, exc: Exception) -> None:
    """Map OpenAI SDK exceptions into the provider exception hierarchy."""
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
