"""TestGen AI v2.3 — ProviderResponse Domain Model

Provider-independent normalized response object returned by all LLM providers.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized provider-agnostic response payload."""

    provider_name: str
    model_name: str
    response_text: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
