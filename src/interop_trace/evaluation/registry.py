"""Registered benchmarks; implementations are imported by this package."""

from interop_trace.components import Registry
from interop_trace.evaluation.base import Benchmark

registry: Registry[Benchmark] = Registry()
