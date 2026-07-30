"""TestGen AI v2.3 — PromptRepository Implementation

Maintains versioned prompt templates organized by agent role.
Supports template lookup, validation, and template registration.
"""

from typing import Dict, List, Optional
import structlog

from app.domain.prompt_template import PromptTemplate
from app.exceptions.v23_exceptions import ValidationError

logger = structlog.get_logger()


# Default Built-In Versioned Templates for TestGen AI v2.3
DEFAULT_TEMPLATES: List[PromptTemplate] = [
    PromptTemplate(
        template_id="planner_v23",
        name="PlannerAgent Template",
        version="v2.3",
        agent="planner",
        description="Generates structured AI-driven unit test planning blueprint in JSON format.",
        system_prompt="""You are a Senior QA Automation Architect. Analyze the source code and repository context to formulate a structured unit test planning blueprint using pytest.

CRITICAL INSTRUCTION: You MUST return ONLY a valid JSON object matching the EXACT schema below. Do NOT include introductory text, conversational remarks, or markdown headers outside the JSON block.

JSON Schema:
{{
  "repository_summary": "Brief summary of the code and repository structure",
  "priority_modules": ["List of core modules to test"],
  "recommended_test_types": ["unit", "integration"],
  "target_functions": ["List of function names to test"],
  "test_cases": [
    {{
      "case_id": 1,
      "description": "Detailed test case description",
      "target_function": "function_name",
      "test_type": "unit",
      "expected_behavior": "Expected outcome"
    }}
  ],
  "required_mocks": ["List of external services/modules to mock"],
  "required_fixtures": ["List of pytest fixtures needed"],
  "edge_cases": ["List of boundary conditions and edge cases"],
  "confidence": 0.95
}}""",
        user_prompt="""Target Source Code:
{source_code}

Repository Context:
{repository_context}

Framework Target: {framework}
Language: {language}

Formulate the structured JSON test plan now.""",
        required_variables=["source_code", "repository_context"],
        optional_variables=["framework", "language"],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="planner_repair_v23",
        name="Planner Repair Template",
        version="v2.3",
        agent="planner_repair",
        description="Repairs malformed or invalid JSON planner output.",
        system_prompt="""You are a JSON Repair Assistant. Fix the provided text so that it becomes a perfectly valid JSON object adhering to the planner schema.""",
        user_prompt="""Malformed Output:
{raw_output}

Parsing Error:
{error_message}

Return ONLY the corrected, valid JSON object.""",
        required_variables=["raw_output", "error_message"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="generator_v23",
        name="GeneratorAgent Template",
        version="v2.3",
        agent="generator",
        description="Generates executable pytest test cases in structured JSON format based on a TestPlan.",
        system_prompt="""You are a Principal Software Engineer in Test. Generate clean, robust, executable pytest unit tests for Python based on the provided TestPlan and RepositoryContext.

CRITICAL INSTRUCTION: You MUST return ONLY a valid JSON object matching the EXACT schema below. Do NOT include introductory text, conversational remarks, or markdown headers outside the JSON block.

JSON Schema:
{{
  "generated_tests": [
    {{
      "target_module": "math_utils",
      "target_function": "add",
      "framework": "pytest",
      "imports": [
        "pytest",
        "from app.math_utils import add"
      ],
      "fixtures": [],
      "mocks": [],
      "test_name": "test_add_positive_numbers",
      "setup": "",
      "test_code": "def test_add_positive_numbers():\\n    assert add(2, 3) == 5",
      "assertions": [
        "assert add(2, 3) == 5"
      ],
      "confidence": 0.96
    }}
  ]
}}""",
        user_prompt="""Source Code:
{source_code}

Test Plan Blueprint:
{test_plan}

Repository Context:
{repository_context}

Generate the structured JSON test cases now.""",
        required_variables=["source_code", "test_plan", "repository_context"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="generator_repair_v23",
        name="Generator Repair Template",
        version="v2.3",
        agent="generator_repair",
        description="Repairs malformed or invalid JSON generator output.",
        system_prompt="""You are a JSON Repair Assistant. Fix the provided text so that it becomes a perfectly valid JSON object adhering to the generator schema.""",
        user_prompt="""Malformed Output:
{raw_output}

Parsing Error:
{error_message}

Return ONLY the corrected, valid JSON object.""",
        required_variables=["raw_output", "error_message"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="reviewer_v23",
        name="ReviewerAgent Template",
        version="v2.3",
        agent="reviewer",
        description="Performs static review of generated test code in structured JSON format.",
        system_prompt="""You are a Test Code Auditor. Inspect the candidate unit tests for syntax, logical flaws, missing assertions, and test smells.

CRITICAL INSTRUCTION: You MUST return ONLY a valid JSON object matching the EXACT schema below. Do NOT include introductory text, conversational remarks, or markdown headers outside the JSON block.

JSON Schema:
{{
  "overall_score": 92,
  "approved": true,
  "summary": "High quality unit test suite.",
  "coverage_analysis": "Target functions covered.",
  "issues": [
    {{
      "severity": "medium",
      "category": "assertion",
      "description": "Missing negative test case",
      "recommendation": "Add test case with invalid input"
    }}
  ],
  "strengths": [
    "Clean assertions"
  ],
  "recommendations": [
    "Add edge case test"
  ],
  "confidence": 0.95
}}""",
        user_prompt="""Candidate Unit Tests:
{candidate_code}

Original Source Code:
{source_code}

Evaluate candidate code quality and return the structured JSON review now.""",
        required_variables=["candidate_code", "source_code"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="reviewer_repair_v23",
        name="Reviewer Repair Template",
        version="v2.3",
        agent="reviewer_repair",
        description="Repairs malformed or invalid JSON reviewer output.",
        system_prompt="""You are a JSON Repair Assistant. Fix the provided text so that it becomes a perfectly valid JSON object adhering to the reviewer schema.""",
        user_prompt="""Malformed Output:
{raw_output}

Parsing Error:
{error_message}

Return ONLY the corrected, valid JSON object.""",
        required_variables=["raw_output", "error_message"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="repair_v23",
        name="RepairAgent Template",
        version="v2.3",
        agent="repair",
        description="Formulates surgical repair code for failing or unapproved test cases in structured JSON format.",
        system_prompt="""You are an Expert Test Repair Specialist. Surgically repair unapproved test cases based on review diagnostics and flaws.

CRITICAL INSTRUCTION: You MUST return ONLY a valid JSON object matching the EXACT schema below. Do NOT include introductory text, conversational remarks, or markdown headers outside the JSON block.

JSON Schema:
{{
  "repaired_tests": [
    {{
      "test_name": "test_add_positive_numbers",
      "target_function": "add",
      "test_code": "def test_add_positive_numbers():\\n    assert add(2, 3) == 5\\n    assert add(-1, 1) == 0\\n",
      "repair_reason": "Added missing negative boundary assertion",
      "fixed_issues": [
        "Missing negative assertion"
      ],
      "confidence": 0.96
    }}
  ]
}}""",
        user_prompt="""Original Test Code:
{candidate_code}

Review Flaws / Errors:
{flaws}

Repository Context:
{repository_context}

Provide the surgical JSON test repairs now.""",
        required_variables=["candidate_code", "flaws", "repository_context"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
    PromptTemplate(
        template_id="repair_repair_v23",
        name="Repair Repair Template",
        version="v2.3",
        agent="repair_repair",
        description="Repairs malformed or invalid JSON repair output.",
        system_prompt="""You are a JSON Repair Assistant. Fix the provided text so that it becomes a perfectly valid JSON object adhering to the repair schema.""",
        user_prompt="""Malformed Output:
{raw_output}

Parsing Error:
{error_message}

Return ONLY the corrected, valid JSON object.""",
        required_variables=["raw_output", "error_message"],
        optional_variables=[],
        metadata={"author": "TestGen AI Architecture Board"},
    ),
]


class PromptRepository:
    """Repository storing and serving versioned PromptTemplate objects."""

    def __init__(self) -> None:
        self._templates: Dict[str, PromptTemplate] = {}
        self.logger = logger.bind(component="PromptRepository")
        
        # Register default v2.3 templates
        for t in DEFAULT_TEMPLATES:
            self.register_template(t)
            
        self.logger.info("prompt_repository_initialized", template_count=len(self._templates))

    def register_template(self, template: PromptTemplate) -> None:
        """Register a PromptTemplate into the repository."""
        key = f"{template.agent}:{template.version}"
        self._templates[key] = template
        self.logger.info("template_registered", key=key, name=template.name)

    def get_template(self, agent_name: str, version: str = "v2.3") -> PromptTemplate:
        """Retrieve PromptTemplate by agent name and version.

        Args:
            agent_name: Name of the agent (planner, generator, reviewer, repair).
            version: Template version string (default: "v2.3").

        Returns:
            Matching PromptTemplate.

        Raises:
            ValidationError: If template is not found.
        """
        key = f"{agent_name.lower()}:{version}"
        template = self._templates.get(key)
        if not template:
            self.logger.error("template_not_found", key=key)
            raise ValidationError("template", f"PromptTemplate not found for key: '{key}'")
        return template
