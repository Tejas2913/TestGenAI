"""Assembled prompt components for LLM consumption."""

from pydantic import BaseModel, Field


class PromptPayload(BaseModel):
    """The three-part prompt sent to the LLM provider."""

    system_prompt: str = Field(description="System-level role and behavior instructions")
    developer_prompt: str = Field(
        description="Structural instructions including output schema"
    )
    user_prompt: str = Field(
        description="User-provided source code and specification"
    )
