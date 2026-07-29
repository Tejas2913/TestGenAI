"""Collection of test cases for a single function."""

from pydantic import BaseModel, Field

from app.domain.test_case import TestCase


class TestSuite(BaseModel):
    """A complete set of tests generated for a target function."""

    function_name: str = Field(description="Name of the function under test")
    test_cases: list[TestCase] = Field(
        default_factory=list, description="Generated test cases"
    )
    imports: list[str] = Field(
        default_factory=list, description="Required import statements"
    )
    setup_code: str | None = Field(
        default=None, description="Shared setup/fixture code"
    )
