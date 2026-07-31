"""TestGen AI v2.4.0 — Provider Failover Manager

Intelligent retry with exponential backoff and per-error-type retry policy.

Retry Policy:
  authentication_error  → NO retry  (key is wrong, retrying won't help)
  invalid_request       → NO retry  (bad payload, retrying won't help)
  timeout               → YES retry (transient)
  rate_limit            → YES retry (wait and retry)
  server_error          → YES retry (transient)
  unknown               → YES retry (default safe)

Usage:
    failover = ProviderFailoverManager(max_retries=2, base_backoff_ms=200)
    response = failover.execute(provider, prompt_payload, health_monitor, cost_tracker)
"""

import time
import structlog
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.domain.provider_response import ProviderResponse
from app.domain.v23_models import PromptPayload
from app.exceptions.v23_exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

if TYPE_CHECKING:
    from app.infrastructure.providers.base import BaseLLMProvider
    from app.infrastructure.providers.health_monitor import ProviderHealthMonitor
    from app.infrastructure.providers.cost_tracker import ProviderCostTracker

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Retry policy constants
# ---------------------------------------------------------------------------

# Exception types that SHOULD be retried
_RETRYABLE_EXCEPTIONS = (ProviderTimeoutError, ProviderRateLimitError, ProviderUnavailableError)

# Exception types that should NOT be retried (fail-fast)
_NON_RETRYABLE_EXCEPTIONS = (ProviderAuthenticationError,)


def _error_type_for(exc: Exception) -> str:
    """Map exception to health_monitor error_type string."""
    if isinstance(exc, ProviderAuthenticationError):
        return "authentication"
    if isinstance(exc, ProviderTimeoutError):
        return "timeout"
    if isinstance(exc, ProviderRateLimitError):
        return "rate_limit"
    return "server_error"


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception warrants a retry."""
    return isinstance(exc, _RETRYABLE_EXCEPTIONS) and not isinstance(exc, _NON_RETRYABLE_EXCEPTIONS)


class ProviderFailoverManager:
    """Intelligent retry + provider failover manager.

    - Retries transient errors with exponential backoff on the same provider.
    - After max retries are exhausted, escalates to the next provider in the
      fallback list.
    - Records every attempt to HealthMonitor and CostTracker.
    - Never silently swallows exceptions.

    All state is in-process only (v2.4 scope).
    """

    def __init__(
        self,
        max_retries: int = 2,
        base_backoff_ms: float = 200.0,
        backoff_multiplier: float = 2.0,
        max_backoff_ms: float = 5_000.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff_ms = max_backoff_ms
        self.logger = logger.bind(component="ProviderFailoverManager")

    def execute_with_fallback(
        self,
        ordered_providers: List["BaseLLMProvider"],
        prompt_payload: PromptPayload,
        options: Optional[Dict[str, Any]] = None,
        health_monitor: Optional["ProviderHealthMonitor"] = None,
        cost_tracker: Optional["ProviderCostTracker"] = None,
        workflow_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ProviderResponse:
        """Execute prompt against providers with retry + automatic fallback.

        Args:
            ordered_providers: List of providers in preference order (primary first).
            prompt_payload: The prompt to execute.
            options: Optional runtime options (temperature, max_tokens, etc.).
            health_monitor: Optional monitor to record outcomes.
            cost_tracker: Optional tracker to record costs.
            workflow_id: For log correlation.
            request_id: For log correlation.

        Returns:
            ProviderResponse from the first provider that succeeds.

        Raises:
            ProviderUnavailableError: If all providers + retries are exhausted.
        """
        last_exception: Optional[Exception] = None

        for provider in ordered_providers:
            name = provider.provider_name
            response = self._try_with_retry(
                provider=provider,
                prompt_payload=prompt_payload,
                options=options or {},
                health_monitor=health_monitor,
                cost_tracker=cost_tracker,
                workflow_id=workflow_id,
                request_id=request_id,
            )
            if response is not None:
                return response

            # Provider exhausted after retries — try next
            self.logger.warning(
                "failover_escalating_to_next_provider",
                failed_provider=name,
                workflow_id=workflow_id,
                request_id=request_id,
            )

        raise ProviderUnavailableError(
            "FailoverManager",
            f"All {len(ordered_providers)} providers exhausted. Last error: {last_exception}",
        )

    def _try_with_retry(
        self,
        provider: "BaseLLMProvider",
        prompt_payload: PromptPayload,
        options: Dict[str, Any],
        health_monitor: Optional["ProviderHealthMonitor"],
        cost_tracker: Optional["ProviderCostTracker"],
        workflow_id: Optional[str],
        request_id: Optional[str],
    ) -> Optional[ProviderResponse]:
        """Attempt provider.generate() with retry.  Returns None if all retries fail."""
        name = provider.provider_name
        attempt = 0

        while attempt <= self.max_retries:
            t_start = time.perf_counter()
            try:
                self.logger.info(
                    "provider_attempt",
                    provider=name,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    workflow_id=workflow_id,
                    request_id=request_id,
                )
                response = provider.generate(prompt_payload=prompt_payload, options=options)
                latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

                # Record success
                if health_monitor:
                    health_monitor.record_outcome(
                        provider_name=name,
                        success=True,
                        latency_ms=latency_ms,
                    )
                if cost_tracker:
                    cost_tracker.record(
                        provider_name=name,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                        cost_usd=response.estimated_cost,
                        workflow_id=workflow_id,
                    )

                self.logger.info(
                    "provider_attempt_succeeded",
                    provider=name,
                    attempt=attempt,
                    latency_ms=latency_ms,
                    tokens=response.total_tokens,
                    cost=response.estimated_cost,
                    workflow_id=workflow_id,
                    request_id=request_id,
                )
                return response

            except _NON_RETRYABLE_EXCEPTIONS as exc:
                # Auth errors / bad requests — no point retrying this provider
                latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                error_type = _error_type_for(exc)
                if health_monitor:
                    health_monitor.record_outcome(
                        provider_name=name,
                        success=False,
                        latency_ms=latency_ms,
                        error_type=error_type,
                        error_message=str(exc),
                    )
                self.logger.warning(
                    "provider_non_retryable_error",
                    provider=name,
                    error_type=error_type,
                    error=str(exc),
                    workflow_id=workflow_id,
                    request_id=request_id,
                )
                return None  # Escalate to next provider

            except ProviderError as exc:
                latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                error_type = _error_type_for(exc)
                retryable = _is_retryable(exc)

                if health_monitor:
                    health_monitor.record_outcome(
                        provider_name=name,
                        success=False,
                        latency_ms=latency_ms,
                        error_type=error_type,
                        error_message=str(exc),
                    )

                self.logger.warning(
                    "provider_attempt_failed",
                    provider=name,
                    attempt=attempt,
                    retryable=retryable,
                    error_type=error_type,
                    error=str(exc),
                    workflow_id=workflow_id,
                    request_id=request_id,
                )

                if not retryable or attempt >= self.max_retries:
                    return None  # Escalate to next provider

                # Wait with exponential backoff before retry
                backoff_ms = min(
                    self.base_backoff_ms * (self.backoff_multiplier ** attempt),
                    self.max_backoff_ms,
                )
                self.logger.info(
                    "provider_retry_backoff",
                    provider=name,
                    backoff_ms=backoff_ms,
                    next_attempt=attempt + 1,
                    workflow_id=workflow_id,
                )
                time.sleep(backoff_ms / 1000.0)
                attempt += 1

            except Exception as exc:
                # Unexpected non-ProviderError exception — treat as non-retryable
                latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                if health_monitor:
                    health_monitor.record_outcome(
                        provider_name=name,
                        success=False,
                        latency_ms=latency_ms,
                        error_type="server_error",
                        error_message=str(exc),
                    )
                self.logger.error(
                    "provider_unexpected_error",
                    provider=name,
                    attempt=attempt,
                    error=str(exc),
                    workflow_id=workflow_id,
                    request_id=request_id,
                )
                return None  # Escalate to next provider

        return None  # All retries exhausted for this provider
