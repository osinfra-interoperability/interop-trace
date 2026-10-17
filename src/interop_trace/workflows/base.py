"""Contracts for running analyses and describing their native outputs."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from interop_trace.databases import Database
from interop_trace.datasets import Dataset


@dataclass(frozen=True)
class WorkflowResult:
    """Named native output files, including settings or logs when applicable.

    ``format`` identifies the output dialect understood by a benchmark reader.
    The workflow defines the file names/roles and returns absolute paths in
    ``files``. This record does not normalize tables or validate their contents.
    """

    format: str
    files: Mapping[str, Path]


class Workflow(Protocol):
    """An analysis configured with its own software version and parameters."""

    def run(
        self, dataset: Dataset, database: Database, *, output_dir: Path
    ) -> WorkflowResult:
        """Analyse the supplied inputs and write outputs under ``output_dir``.

        Input parsing and validation may be delegated to the analysis tool.
        Implementations must raise on execution failure. Successful execution
        does not establish scientific accuracy.
        """
        ...
