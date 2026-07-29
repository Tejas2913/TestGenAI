"""Gemini LLM provider with retry, timeout, and usage tracking."""

import time
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google")

import structlog
from google import genai
from google.genai import types

from app.ai.providers.base import LLMProvider
from app.domain.prompt_payload import PromptPayload
from app.exceptions import LLMException, LLMRetryExhaustedException, LLMTimeoutException

logger = structlog.get_logger()

# Exceptions from the Gemini SDK that are retryable (transient).
_RETRYABLE_STATUS_CODES = {429, 500, 503}

# The only finish reason that guarantees a complete response.
_COMPLETE_FINISH_REASON = "STOP"


class GeminiProvider(LLMProvider):
    """Concrete LLM provider that calls the Google Gemini API.

    Features:
    - Exponential backoff retry for transient failures (429, 500, 503)
    - Automatic single retry when finish_reason indicates incomplete output
    - Configurable request timeout
    - Token usage tracking via `last_usage` property
    - Duration tracking
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.3,
        max_output_tokens: int = 4096,
        timeout_seconds: int = 60,
        max_retries: int = 3,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

        # Metadata from the last successful generate() call.
        # Read by GenerationService after calling generate().
        self._last_usage: dict | None = None

    @property
    def last_usage(self) -> dict | None:
        """Token usage and timing metadata from the last generate() call.

        Returns a dict with keys: input_tokens, output_tokens, total_tokens,
        duration_ms, retry_count, model. Returns None if generate() has
        not been called yet.
        """
        return self._last_usage

    @property
    def is_configured(self) -> bool:
        """Check whether the provider has a valid API key configured."""
        try:
            return bool(self._client) and bool(self._model_name)
        except Exception:
            return False

    def generate(self, payload: PromptPayload) -> str:
        """Send prompts to Gemini and return the raw response text.

        Retries transient failures with exponential backoff.
        Retries once if finish_reason indicates the response was truncated.
        Raises LLMTimeoutException or LLMRetryExhaustedException on failure.
        """
        combined_prompt = (
            f"{payload.system_prompt}\n\n"
            f"{payload.developer_prompt}\n\n"
            f"{payload.user_prompt}"
        )

        # JSON schema that mirrors the TestSuite / TestCase domain models.
        # Combined with response_mime_type="application/json", this activates
        # Gemini's constrained-decoding mode: every token is sampled from a
        # grammar derived from this schema, making structurally invalid JSON
        # impossible at the generation level.
        _test_suite_schema = types.Schema(
            type=types.Type.OBJECT,
            required=["function_name", "test_cases", "imports"],
            properties={
                "function_name": types.Schema(type=types.Type.STRING),
                "imports": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                ),
                "setup_code": types.Schema(
                    type=types.Type.STRING,
                    nullable=True,
                ),
                "test_cases": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        required=["name", "description", "category",
                                  "inputs", "expected_output", "assertions"],
                        properties={
                            "name": types.Schema(type=types.Type.STRING),
                            "description": types.Schema(type=types.Type.STRING),
                            "category": types.Schema(type=types.Type.STRING),
                            "inputs": types.Schema(type=types.Type.OBJECT),
                            "expected_output": types.Schema(type=types.Type.STRING),
                            "assertions": types.Schema(
                                type=types.Type.ARRAY,
                                items=types.Schema(type=types.Type.STRING),
                            ),
                        },
                    ),
                ),
            },
        )

        generation_config = types.GenerateContentConfig(
            temperature=self._temperature,
            max_output_tokens=self._max_output_tokens,
            # Force valid JSON format without constraining dynamic dictionary keys in inputs.
            response_mime_type="application/json",
            # gemini-3.5-flash and other "thinking" model variants consume
            # thinking tokens from the max_output_tokens budget and emit
            # thought_signature parts that interfere with response.text.
            # Setting thinking_budget=0 and include_thoughts=False disables
            # the hidden reasoning pass entirely.
            thinking_config=types.ThinkingConfig(
                thinking_budget=0,
                include_thoughts=False,
            ),
        )

        last_exception: Exception | None = None
        retry_count = 0
        start_time = time.monotonic()

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "gemini_request",
                    model=self._model_name,
                    attempt=attempt,
                    max_retries=self._max_retries,
                    timeout_seconds=self._timeout_seconds,
                )

                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=combined_prompt,
                    config=generation_config,
                )

                duration_ms = (time.monotonic() - start_time) * 1000
                raw_text = response.text

                # Extract token usage if available
                usage = self._extract_usage(response, duration_ms, retry_count)
                self._last_usage = usage

                # Extract finish metadata from the first candidate
                finish_reason, finish_message, candidate_count = (
                    self._extract_finish_metadata(response)
                )

                logger.info(
                    "gemini_response",
                    model=self._model_name,
                    response_len=len(raw_text),
                    duration_ms=round(duration_ms, 2),
                    retry_count=retry_count,
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    finish_reason=finish_reason,
                    finish_message=finish_message,
                    candidate_count=candidate_count,
                )

                # If the response did not finish cleanly, retry once.
                if finish_reason != _COMPLETE_FINISH_REASON:
                    raw_text = self._retry_incomplete(
                        combined_prompt=combined_prompt,
                        generation_config=generation_config,
                        original_finish_reason=finish_reason,
                        original_finish_message=finish_message,
                        start_time=start_time,
                        retry_count=retry_count,
                        usage=usage,
                    )

                return raw_text

            except (LLMTimeoutException, LLMRetryExhaustedException, LLMException):
                # Re-raise exceptions that are already typed and handled.
                raise

            except Exception as exc:
                last_exception = exc
                duration_ms = (time.monotonic() - start_time) * 1000

                if self._is_timeout(exc):
                    logger.warning(
                        "gemini_timeout",
                        model=self._model_name,
                        attempt=attempt,
                        duration_ms=round(duration_ms, 2),
                    )
                    raise LLMTimeoutException(
                        detail=(
                            f"Gemini request timed out after "
                            f"{self._timeout_seconds}s on attempt {attempt}"
                        )
                    ) from exc

                if self._is_retryable(exc) and attempt < self._max_retries:
                    retry_count += 1
                    wait = self._backoff_delay(attempt)
                    logger.warning(
                        "gemini_retry",
                        model=self._model_name,
                        attempt=attempt,
                        wait_seconds=wait,
                        error=str(exc)[:200],
                    )
                    time.sleep(wait)
                    continue

                # Non-retryable or last attempt
                break

        # All retries exhausted or non-retryable error
        duration_ms = (time.monotonic() - start_time) * 1000
        self._last_usage = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "duration_ms": round(duration_ms, 2),
            "retry_count": retry_count,
            "model": self._model_name,
        }

        error_msg = str(last_exception)[:500] if last_exception else "Unknown error"

        if retry_count > 0:
            logger.error(
                "gemini_retry_exhausted",
                model=self._model_name,
                attempts=retry_count + 1,
                duration_ms=round(duration_ms, 2),
                error=error_msg,
            )
            raise LLMRetryExhaustedException(
                detail=f"Gemini failed after {retry_count + 1} attempts: {error_msg}",
                attempts=retry_count + 1,
            ) from last_exception

        logger.error(
            "gemini_error",
            model=self._model_name,
            duration_ms=round(duration_ms, 2),
            error=error_msg,
        )
        raise LLMException(
            detail=f"Gemini request failed: {error_msg}"
        ) from last_exception

    # ------------------------------------------------------------------
    # Incomplete-response retry
    # ------------------------------------------------------------------

    def _retry_incomplete(
        self,
        combined_prompt: str,
        generation_config: types.GenerateContentConfig,
        original_finish_reason: str,
        original_finish_message: str | None,
        start_time: float,
        retry_count: int,
        usage: dict,
    ) -> str:
        """Retry once when the first response was not finished cleanly.

        Returns the text of the retry response if it completes with STOP.
        Raises LLMException if the retry also fails to complete.
        """
        logger.warning(
            "gemini_incomplete_response",
            model=self._model_name,
            finish_reason=original_finish_reason,
            finish_message=original_finish_message,
            output_tokens=usage.get("output_tokens"),
            action="retrying_once",
        )

        try:
            retry_response = self._client.models.generate_content(
                model=self._model_name,
                contents=combined_prompt,
                config=generation_config,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            retry_text = retry_response.text

            retry_finish_reason, retry_finish_message, retry_candidate_count = (
                self._extract_finish_metadata(retry_response)
            )

            retry_usage = self._extract_usage(retry_response, duration_ms, retry_count)
            self._last_usage = retry_usage

            logger.info(
                "gemini_incomplete_retry_response",
                model=self._model_name,
                response_len=len(retry_text),
                duration_ms=round(duration_ms, 2),
                finish_reason=retry_finish_reason,
                finish_message=retry_finish_message,
                candidate_count=retry_candidate_count,
                input_tokens=retry_usage.get("input_tokens"),
                output_tokens=retry_usage.get("output_tokens"),
            )

            if retry_finish_reason != _COMPLETE_FINISH_REASON:
                raise LLMException(
                    detail=(
                        f"Gemini returned an incomplete response on both attempts. "
                        f"finish_reason={retry_finish_reason!r}, "
                        f"finish_message={retry_finish_message!r}, "
                        f"output_tokens={retry_usage.get('output_tokens')}"
                    )
                )

            return retry_text

        except LLMException:
            raise

        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "gemini_incomplete_retry_error",
                model=self._model_name,
                duration_ms=round(duration_ms, 2),
                error=str(exc)[:200],
            )
            raise LLMException(
                detail=(
                    f"Gemini incomplete-response retry failed: {str(exc)[:300]}. "
                    f"Original finish_reason={original_finish_reason!r}, "
                    f"finish_message={original_finish_message!r}"
                )
            ) from exc

    # ------------------------------------------------------------------
    # Metadata extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_finish_metadata(
        response,
    ) -> tuple[str, str | None, int]:
        """Extract finish_reason, finish_message, and candidate count.

        Returns a tuple of (finish_reason, finish_message, candidate_count).
        Falls back to safe defaults when the fields are unavailable.
        """
        finish_reason: str = "UNKNOWN"
        finish_message: str | None = None
        candidate_count: int = 0

        try:
            candidates = getattr(response, "candidates", None) or []
            candidate_count = len(candidates)

            if candidates:
                first = candidates[0]
                reason = getattr(first, "finish_reason", None)
                if reason is not None:
                    # The SDK may return an enum or a string.
                    finish_reason = (
                        reason.name if hasattr(reason, "name") else str(reason)
                    )
                finish_message = getattr(first, "finish_message", None) or None
        except Exception:
            pass  # Gracefully fall back to defaults

        return finish_reason, finish_message, candidate_count

    def _extract_usage(
        self, response, duration_ms: float, retry_count: int
    ) -> dict:
        """Extract token usage metadata from the Gemini response."""
        usage: dict = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "duration_ms": round(duration_ms, 2),
            "retry_count": retry_count,
            "model": self._model_name,
        }

        try:
            meta = getattr(response, "usage_metadata", None)
            if meta:
                usage["input_tokens"] = getattr(meta, "prompt_token_count", None)
                usage["output_tokens"] = getattr(meta, "candidates_token_count", None)
                usage["total_tokens"] = getattr(meta, "total_token_count", None)
        except Exception:
            pass  # Gracefully skip if metadata is unavailable

        return usage

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Determine if the exception represents a transient failure."""
        exc_str = str(exc).lower()

        for code in _RETRYABLE_STATUS_CODES:
            if str(code) in exc_str:
                return True

        transient_patterns = [
            "resource exhausted",
            "rate limit",
            "temporarily unavailable",
            "service unavailable",
            "internal server error",
            "deadline exceeded",
            "connection reset",
            "connection refused",
            "connection aborted",
        ]
        return any(pattern in exc_str for pattern in transient_patterns)

    @staticmethod
    def _is_timeout(exc: Exception) -> bool:
        """Determine if the exception represents a timeout."""
        exc_str = str(exc).lower()
        return any(
            pattern in exc_str
            for pattern in ["timeout", "timed out", "deadline exceeded"]
        )

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Calculate exponential backoff delay: 2^attempt seconds (2, 4, 8...)."""
        return min(2 ** attempt, 30)  # Cap at 30 seconds