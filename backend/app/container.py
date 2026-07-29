"""TestGen AI v2.3 — Dependency Injection Container

Wires agents, infrastructure services, routing strategies, indexers, and workflow orchestrators
for application-wide dependency injection.
"""

from typing import Optional
import structlog

from app.agents.generator import GeneratorAgent
from app.agents.planner import PlannerAgent
from app.agents.repair import RepairAgent
from app.agents.reviewer import ReviewerAgent
from app.infrastructure.indexers.repository_index import RepositoryContextIndex
from app.infrastructure.routing_strategies.strategies import BalancedStrategy
from app.infrastructure.services import (
    ContextCache,
    LLMProviderRouter,
    PromptBuilder,
    PromptManager,
    PromptRepository,
    ProviderEvaluator,
    ReasoningTraceLogger,
    TokenCostTracker,
)
from app.workflows.agent_workflow import AgentWorkflow

logger = structlog.get_logger()


class ApplicationContainer:
    """IoC Container providing singleton instances of infrastructure and workflow services."""

    def __init__(self) -> None:
        self.logger = logger.bind(component="ApplicationContainer")

        # Infrastructure
        self.context_cache = ContextCache()
        self.repository_index = RepositoryContextIndex()
        self.prompt_repository = PromptRepository()
        self.prompt_builder = PromptBuilder()
        self.prompt_manager = PromptManager(self.prompt_repository, self.prompt_builder)

        # Routing & LLM Providers
        self.routing_strategy = BalancedStrategy()
        self.provider_evaluator = ProviderEvaluator(default_strategy=self.routing_strategy)
        self.provider_router = LLMProviderRouter(evaluator=self.provider_evaluator)

        # Analytics
        self.token_cost_tracker = TokenCostTracker()
        self.reasoning_trace_logger = ReasoningTraceLogger()

        # Agents
        self.planner_agent = PlannerAgent()
        self.generator_agent = GeneratorAgent()
        self.reviewer_agent = ReviewerAgent()
        self.repair_agent = RepairAgent()

        # Agent Workflow
        self.agent_workflow = AgentWorkflow(
            agents=[
                self.planner_agent,
                self.generator_agent,
                self.reviewer_agent,
                self.repair_agent,
            ]
        )

        self.logger.info("container_initialized")


_container_instance: Optional[ApplicationContainer] = None


def get_container() -> ApplicationContainer:
    """Retrieve global ApplicationContainer singleton instance."""
    global _container_instance
    if _container_instance is None:
        _container_instance = ApplicationContainer()
    return _container_instance
