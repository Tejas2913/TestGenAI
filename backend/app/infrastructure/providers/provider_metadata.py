"""TestGen AI v2.4.0 — Centralized Provider Metadata Registry

Single source of truth for all LLM provider capabilities, costs, and performance characteristics.

Adding a new provider requires ONLY:
  1. A new ProviderMetadata entry in PROVIDER_METADATA
  2. The provider class implementation
  3. Router registration

No routing logic, health monitor, failover manager, or cost tracker requires modification.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class ProviderMetadata:
    """Immutable metadata descriptor for a single LLM provider."""

    provider_name: str
    default_model: str

    # Context / output limits
    context_window: int           # tokens
    max_output_tokens: int        # tokens

    # Capability flags
    supports_streaming: bool = False
    supports_json: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_reasoning: bool = False

    # Cost (USD per 1 000 tokens)
    estimated_input_cost: float = 0.001
    estimated_output_cost: float = 0.002

    # Performance benchmarks (empirical averages)
    typical_latency_ms: float = 500.0

    # Quality score 0.0–1.0 (subjective benchmark average across coding tasks)
    quality_score: float = 0.80

    # Availability / tier
    availability: str = "production"   # "production" | "beta" | "experimental"
    requires_api_key: bool = True


# ---------------------------------------------------------------------------
# Central Metadata Registry
# ---------------------------------------------------------------------------
# Every supported provider must have an entry here.
# Keys MUST match BaseLLMProvider.provider_name exactly.

PROVIDER_METADATA: Dict[str, ProviderMetadata] = {

    "Gemini": ProviderMetadata(
        provider_name="Gemini",
        default_model="gemini-2.0-flash",
        context_window=1_000_000,
        max_output_tokens=8_192,
        supports_streaming=True,
        supports_json=True,
        supports_vision=True,
        supports_function_calling=True,
        supports_reasoning=True,          # Gemini 2.x thinking models
        estimated_input_cost=0.00015,     # $0.15 / 1M tokens
        estimated_output_cost=0.00060,    # $0.60 / 1M tokens
        typical_latency_ms=800.0,
        quality_score=0.88,
        availability="production",
    ),

    "OpenAI": ProviderMetadata(
        provider_name="OpenAI",
        default_model="gpt-4o",
        context_window=128_000,
        max_output_tokens=16_384,
        supports_streaming=True,
        supports_json=True,
        supports_vision=True,
        supports_function_calling=True,
        supports_reasoning=True,          # o1 / o3 series
        estimated_input_cost=0.0025,      # $2.50 / 1M tokens
        estimated_output_cost=0.010,      # $10.00 / 1M tokens
        typical_latency_ms=1_200.0,
        quality_score=0.92,
        availability="production",
    ),

    "Claude": ProviderMetadata(
        provider_name="Claude",
        default_model="claude-3-5-sonnet-20241022",
        context_window=200_000,
        max_output_tokens=8_192,
        supports_streaming=True,
        supports_json=True,
        supports_vision=True,
        supports_function_calling=True,
        supports_reasoning=True,          # Claude 3.5 shows strong reasoning
        estimated_input_cost=0.003,       # $3.00 / 1M tokens
        estimated_output_cost=0.015,      # $15.00 / 1M tokens
        typical_latency_ms=1_500.0,
        quality_score=0.94,
        availability="production",
    ),

    "Groq": ProviderMetadata(
        provider_name="Groq",
        default_model="llama-3.3-70b-versatile",
        context_window=128_000,
        max_output_tokens=32_768,
        supports_streaming=True,
        supports_json=True,
        supports_vision=False,
        supports_function_calling=True,
        supports_reasoning=False,
        estimated_input_cost=0.00059,     # $0.59 / 1M tokens
        estimated_output_cost=0.00079,    # $0.79 / 1M tokens
        typical_latency_ms=250.0,         # Groq LPU is extremely fast
        quality_score=0.82,
        availability="production",
    ),

    "OpenRouter": ProviderMetadata(
        provider_name="OpenRouter",
        default_model="deepseek/deepseek-r1",
        context_window=128_000,
        max_output_tokens=8_000,
        supports_streaming=True,
        supports_json=True,
        supports_vision=False,
        supports_function_calling=False,
        supports_reasoning=True,          # DeepSeek-R1 is a reasoning model
        estimated_input_cost=0.00055,     # $0.55 / 1M tokens
        estimated_output_cost=0.00219,    # $2.19 / 1M tokens
        typical_latency_ms=2_000.0,
        quality_score=0.86,
        availability="production",
    ),
}


def get_metadata(provider_name: str) -> ProviderMetadata:
    """Return metadata for a named provider. Raises KeyError if not registered."""
    meta = PROVIDER_METADATA.get(provider_name)
    if meta is None:
        raise KeyError(
            f"Provider '{provider_name}' not found in PROVIDER_METADATA. "
            f"Available: {sorted(PROVIDER_METADATA.keys())}"
        )
    return meta


def list_providers() -> list:
    """Return sorted list of all registered provider names."""
    return sorted(PROVIDER_METADATA.keys())


def filter_by_capability(capability: str) -> list:
    """Return provider names that have the given boolean capability set to True.

    Example:
        filter_by_capability("supports_streaming")
        → ["Claude", "Gemini", "Groq", "OpenAI", "OpenRouter"]
    """
    return [
        name for name, meta in PROVIDER_METADATA.items()
        if getattr(meta, capability, False) is True
    ]
