"""Contracts for evaluating a workflow result against a defined benchmark."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.workflows import WorkflowResult


@dataclass(frozen=True)
class EvaluationResult:
    """Named numeric metrics and optional report files at absolute paths.

    Each benchmark defines its metric names, units and interpretation. Metrics
    from different benchmarks are not automatically comparable. Reports may
    contain richer tables or explanations; no universal score is required.
    """

    metrics: Mapping[str, int | float]
    reports: tuple[Path, ...] = ()


class Benchmark(Protocol):
    """An evaluator configured with its own expectations and scoring parameters."""

    def evaluate(
        self,
        result: WorkflowResult,
        dataset: Dataset,
        database: Database,
        *,
        output_dir: Path,
    ) -> EvaluationResult:
        """Score one run, writing any reports under ``output_dir``.

        The supplied dataset and database must be the inputs used for this run.
        Implementations must reject incompatible result formats or experimental
        designs and raise on evaluation failure. The database is not ground truth.
        """
        ...
