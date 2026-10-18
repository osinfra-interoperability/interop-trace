"""Registered dataset providers; implementations are imported by this package."""

from interop_trace.components import Registry
from interop_trace.datasets.base import DatasetProvider

registry: Registry[DatasetProvider] = Registry()
