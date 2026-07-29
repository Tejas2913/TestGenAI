"""TestGen AI v2.3 — Base Agent Framework

Abstract Base Class defining the lifecycle hooks, template execution method, exception handling,
and timing for all cognitive reasoning agents.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
import time
import structlog

from app.domain.v23_models import AgentWorkflowContext
from app.exceptions.v23_exceptions import AgentExecutionError, ValidationError

if TYPE_CHECKING:
    from app.workflows.states import WorkflowState

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Abstract base class for cognitive reasoning agents with lifecycle execution hooks."""

    def __init__(self, agent_name: str, target_state: Optional["WorkflowState"] = None) -> None:
        self.agent_name = agent_name
        self.target_state = target_state
        self.logger = logger.bind(agent=agent_name)

    def before_execute(self, context: AgentWorkflowContext) -> None:
        """Lifecycle hook executed before reasoning logic.

        Args:
            context: Shared AgentWorkflowContext.

        Raises:
            ValidationError: If context is invalid.
        """
        if context is None:
            raise ValidationError("context", "AgentWorkflowContext cannot be None")
        if context.request is None:
            raise ValidationError("request", "GenerationRequest in context cannot be None")

    @abstractmethod
    def execute(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Core reasoning logic implemented by concrete agents.

        Args:
            context: Shared AgentWorkflowContext.

        Returns:
            Updated AgentWorkflowContext.
        """
        pass

    def after_execute(self, context: AgentWorkflowContext) -> None:
        """Lifecycle hook executed after successful reasoning logic."""
        pass

    def run(self, context: AgentWorkflowContext) -> AgentWorkflowContext:
        """Template execution method executing lifecycle hooks, timing, and exception handling.

        Args:
            context: Shared AgentWorkflowContext.

        Returns:
            Updated AgentWorkflowContext.

        Raises:
            AgentExecutionError: Wrapped exception if execution fails.
        """
        start_time = time.perf_counter()
        self.logger.info("agent_execution_started")

        try:
            self.before_execute(context)
            context = self.execute(context)
            self.after_execute(context)
            
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.logger.info("agent_execution_completed", elapsed_ms=elapsed_ms)
            return context

        except ValidationError as ve:
            self.logger.error("agent_validation_failed", error=str(ve))
            raise AgentExecutionError(self.agent_name, str(ve), original_exception=ve)
        except Exception as exc:
            self.logger.error("agent_execution_failed", error=str(exc))
            raise AgentExecutionError(self.agent_name, str(exc), original_exception=exc)
