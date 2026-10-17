"""The four built-in layer registries, shared by configuration and developer tools."""

from typing import Any

from interop_trace.components import Registry
from interop_trace.databases.registry import registry as databases
from interop_trace.datasets.registry import registry as datasets
from interop_trace.evaluation.registry import registry as benchmarks
from interop_trace.workflows.registry import registry as workflows

__all__ = ["REGISTRIES", "benchmarks", "databases", "datasets", "workflows"]

REGISTRIES: dict[str, Registry[Any]] = {
    "datasets": datasets,
    "databases": databases,
    "workflows": workflows,
    "benchmarks": benchmarks,
}
