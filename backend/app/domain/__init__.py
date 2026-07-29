"""Domain models for the TestGen AI pipeline."""

from app.domain.code_metadata import CodeMetadata
from app.domain.generation_result import GenerationResult
from app.domain.parameter import ParameterInfo
from app.domain.prompt_payload import PromptPayload
from app.domain.prompt_template import PromptTemplate
from app.domain.test_case import ALLOWED_CATEGORIES, TestCase
from app.domain.test_suite import TestSuite
from app.domain.v23_models import (
    AgentWorkflowContext,
    CandidateTest,
    GenerationRequest,
    ProviderDecision,
    QualityReport,
    ReasoningTrace,
    RepairAction,
    RepositoryContext,
    ReviewReport,
    TestPlan,
    TokenUsage,
)

__all__ = [
    "ALLOWED_CATEGORIES",
    "AgentWorkflowContext",
    "CandidateTest",
    "CodeMetadata",
    "GenerationRequest",
    "GenerationResult",
    "ParameterInfo",
    "PromptPayload",
    "PromptTemplate",
    "ProviderDecision",
    "QualityReport",
    "ReasoningTrace",
    "RepairAction",
    "RepositoryContext",
    "ReviewReport",
    "TestCase",
    "TestPlan",
    "TestSuite",
    "TokenUsage",
]
