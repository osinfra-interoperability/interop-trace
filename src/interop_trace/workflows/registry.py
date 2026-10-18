"""Registered workflows; implementations are imported by this package."""

from interop_trace.components import Registry
from interop_trace.workflows.base import Workflow

registry: Registry[Workflow] = Registry()
