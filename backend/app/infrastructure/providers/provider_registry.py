"""TestGen AI v2.4.0 — Provider Registry

Centralized capability lookup and provider discovery backed by provider_metadata.py.

The registry is the single source of truth for routing decisions —
no routing strategy should hardcode provider names or capability assumptions.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.infrastructure.providers.provider_metadata import (
    PROVIDER_METADATA,
    ProviderMetadata,
    filter_by_capability,
    get_metadata,
    list_providers,
)


# Re-export ProviderMetadata so callers import from here
__all__ = ["ProviderRegistry", "ProviderCapability", "GLOBAL_REGISTRY"]


@dataclass(frozen=True)
class ProviderCapability:
    """Flattened capability view returned by the registry for a specific provider.

    Used by routing strategies to make decisions without knowing internal
    provider class details.
    """

    provider_name: str
    model_name: str
    context_window: int
    max_output_tokens: int
    supports_streaming: bool
    supports_json: bool
    supports_vision: bool
    supports_function_calling: bool
    supports_reasoning: bool
    estimated_input_cost: float
    estimated_output_cost: float
    typical_latency_ms: float
    quality_score: float
    availability: str

    @classmethod
    def from_metadata(cls, meta: ProviderMetadata) -> "ProviderCapability":
        """Construct from a ProviderMetadata entry."""
        return cls(
            provider_name=meta.provider_name,
            model_name=meta.default_model,
            context_window=meta.context_window,
            max_output_tokens=meta.max_output_tokens,
            supports_streaming=meta.supports_streaming,
            supports_json=meta.supports_json,
            supports_vision=meta.supports_vision,
            supports_function_calling=meta.supports_function_calling,
            supports_reasoning=meta.supports_reasoning,
            estimated_input_cost=meta.estimated_input_cost,
            estimated_output_cost=meta.estimated_output_cost,
            typical_latency_ms=meta.typical_latency_ms,
            quality_score=meta.quality_score,
            availability=meta.availability,
        )


class ProviderRegistry:
    """Central registry for provider capability lookup and filtering.

    Backed by the static PROVIDER_METADATA dict in provider_metadata.py.
    All routing strategies should consult this registry rather than
    hardcoding provider-specific assumptions.
    """

    def get(self, provider_name: str) -> Optional[ProviderCapability]:
        """Return capability descriptor for provider_name, or None if unknown."""
        meta = PROVIDER_METADATA.get(provider_name)
        if meta is None:
            return None
        return ProviderCapability.from_metadata(meta)

    def get_or_raise(self, provider_name: str) -> ProviderCapability:
        """Return capability descriptor or raise KeyError."""
        return ProviderCapability.from_metadata(get_metadata(provider_name))

    def all_providers(self) -> List[str]:
        """Return sorted list of all registered provider names."""
        return list_providers()

    def filter_capable(
        self,
        available: List[str],
        capability: str,
    ) -> List[str]:
        """Return subset of `available` providers that have `capability=True`.

        Args:
            available: Provider names currently registered in the router.
            capability: Attribute name on ProviderMetadata (e.g. "supports_streaming").

        Returns:
            Filtered list preserving original order.
        """
        capable = set(filter_by_capability(capability))
        return [p for p in available if p in capable]

    def rank_by(
        self,
        available: List[str],
        attribute: str,
        ascending: bool = True,
    ) -> List[str]:
        """Return `available` sorted by a numeric metadata attribute.

        Args:
            available: Provider names to rank.
            attribute: Numeric attribute on ProviderMetadata (e.g. "typical_latency_ms").
            ascending: True = lowest first (good for cost/latency), False = highest first (good for quality).

        Returns:
            Sorted list; providers not in PROVIDER_METADATA go to the end.
        """
        def sort_key(name: str):
            meta = PROVIDER_METADATA.get(name)
            if meta is None:
                return float("inf") if ascending else float("-inf")
            return getattr(meta, attribute, 0.0)

        return sorted(available, key=sort_key, reverse=not ascending)

    def capabilities_for_available(
        self, available: List[str]
    ) -> Dict[str, ProviderCapability]:
        """Return dict of name → capability for all available providers."""
        result = {}
        for name in available:
            cap = self.get(name)
            if cap:
                result[name] = cap
        return result

    def supports(self, provider_name: str, capability: str) -> bool:
        """Quick boolean check: does this provider support a given capability?"""
        meta = PROVIDER_METADATA.get(provider_name)
        if meta is None:
            return False
        return bool(getattr(meta, capability, False))


# ---------------------------------------------------------------------------
# Module-level singleton — import this throughout the codebase
# ---------------------------------------------------------------------------
GLOBAL_REGISTRY = ProviderRegistry()
