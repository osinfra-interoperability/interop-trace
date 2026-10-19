"""Analysis workflows and their results."""

from interop_trace.workflows.base import Workflow, WorkflowResult
from interop_trace.workflows.comet import CometWorkflow
from interop_trace.workflows.msamanda import MSAmandaWorkflow
from interop_trace.workflows.sage import SageWorkflow, download_sage

__all__ = [
    "CometWorkflow",
    "MSAmandaWorkflow",
    "SageWorkflow",
    "Workflow",
    "WorkflowResult",
    "download_sage",
]
