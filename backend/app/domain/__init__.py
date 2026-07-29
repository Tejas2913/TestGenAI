"""Domain models for the TestGen AI pipeline."""

from app.domain.code_metadata import CodeMetadata
from app.domain.generation_result import GenerationResult
from app.domain.parameter import ParameterInfo
from app.domain.prompt_payload import PromptPayload
from app.domain.test_case import ALLOWED_CATEGORIES, TestCase
from app.domain.test_suite import TestSuite

__all__ = [
    "ALLOWED_CATEGORIES",
    "CodeMetadata",
    "GenerationResult",
    "ParameterInfo",
    "PromptPayload",
    "TestCase",
    "TestSuite",
]
