"""Source code metadata extracted by the InputAnalyser."""

from pydantic import BaseModel, Field

from app.domain.parameter import ParameterInfo


class CodeMetadata(BaseModel):
    """Structured representation of a Python function's signature and context."""

    function_name: str = Field(description="Name of the function")
    parameters: list[ParameterInfo] = Field(
        default_factory=list, description="Function parameters"
    )
    return_type: str | None = Field(default=None, description="Return type annotation")
    docstring: str | None = Field(default=None, description="Function docstring")
    class_name: str | None = Field(
        default=None, description="Enclosing class name if method"
    )
    decorators: list[str] = Field(
        default_factory=list, description="Applied decorators"
    )
    source_code: str = Field(description="Original source code")
