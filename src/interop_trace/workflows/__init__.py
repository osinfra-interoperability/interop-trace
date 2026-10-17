"""Analysis workflows and their results."""

from interop_trace.workflows.base import Workflow, WorkflowResult
from interop_trace.workflows.sage import SageWorkflow

__all__ = ["SageWorkflow", "Workflow", "WorkflowResult"]
