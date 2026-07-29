"""TestGen AI v2.3 — PromptTemplate Domain Model

Structured, provider-independent model for versioned prompt templates.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PromptTemplate:
    """Provider-independent prompt template domain model."""

    template_id: str
    name: str
    version: str
    agent: str
    description: str
    system_prompt: str
    user_prompt: str
    required_variables: List[str] = field(default_factory=list)
    optional_variables: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
