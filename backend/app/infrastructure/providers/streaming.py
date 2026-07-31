"""TestGen AI v2.4.0 — Streaming Support

Defines StreamChunk and the stream_generate() contract.

stream_generate() yields StreamChunk objects as the provider produces tokens.
BaseLLMProvider provides a default fallback implementation that calls generate()
and wraps the full response in a single chunk — no provider needs to be broken
to support streaming.

Providers that support real streaming override stream_generate() to yield
incremental chunks.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterator, Optional


@dataclass
class StreamChunk:
    """A single incremental chunk produced during streaming generation.

    Attributes:
        provider_name:  Source provider (e.g. "Gemini").
        model_name:     Model identifier.
        delta:          Incremental text content of this chunk.
        accumulated:    Full text accumulated so far (including this chunk).
        finish_reason:  Set on the final chunk ("stop", "length", etc.), else None.
        prompt_tokens:  Populated on the final chunk; None otherwise.
        completion_tokens: Populated on the final chunk; None otherwise.
        total_tokens:   Populated on the final chunk; None otherwise.
        latency_ms:     Total elapsed time; populated on the final chunk.
        estimated_cost: Populated on the final chunk; None otherwise.
        is_final:       True only on the last chunk.
        metadata:       Provider-specific extras.
    """

    provider_name: str
    model_name: str
    delta: str = ""
    accumulated: str = ""
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    estimated_cost: Optional[float] = None
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type alias for stream generators
StreamGenerator = Iterator[StreamChunk]


def stream_from_response(provider_response) -> StreamGenerator:
    """Wrap a completed ProviderResponse as a single-chunk StreamGenerator.

    Used as the default fallback for providers that don't implement native streaming.
    Callers receive exactly one chunk with is_final=True.

    Args:
        provider_response: A ProviderResponse object.

    Yields:
        One StreamChunk containing the full response.
    """
    yield StreamChunk(
        provider_name=provider_response.provider_name,
        model_name=provider_response.model_name,
        delta=provider_response.response_text,
        accumulated=provider_response.response_text,
        finish_reason=provider_response.finish_reason,
        prompt_tokens=provider_response.prompt_tokens,
        completion_tokens=provider_response.completion_tokens,
        total_tokens=provider_response.total_tokens,
        latency_ms=provider_response.latency_ms,
        estimated_cost=provider_response.estimated_cost,
        is_final=True,
        metadata={**provider_response.metadata, "streaming_fallback": True},
    )


def collect_stream(stream: StreamGenerator) -> str:
    """Consume a StreamGenerator and return the full accumulated text.

    Useful when you want streaming internally but need the full string at the end.
    """
    last_accumulated = ""
    for chunk in stream:
        last_accumulated = chunk.accumulated
    return last_accumulated
