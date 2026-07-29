"""Parameter metadata extracted from function signatures."""

from pydantic import BaseModel, Field


class ParameterInfo(BaseModel):
    """Represents a single function parameter with optional type and default."""

    name: str = Field(description="Parameter name")
    type_hint: str | None = Field(default=None, description="Type annotation as string")
    default_value: str | None = Field(
        default=None, description="Default value as string representation"
    )
