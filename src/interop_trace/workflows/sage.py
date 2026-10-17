"""Run the Sage command-line tool with its native JSON configuration."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.workflows.base import WorkflowResult


@dataclass(frozen=True)
class SageWorkflow:
    """A local Sage executable and configuration, with a thread limit.

    ``executable`` is the path to the Sage binary. ``configuration`` is a native
    Sage JSON file. Sage interprets the file contents and scientific settings.
    """

    executable: Path
    configuration: Path
    threads: int = 2

    def run(
        self, dataset: Dataset, database: Database, *, output_dir: Path
    ) -> WorkflowResult:
        """Run Sage in a new directory and return its files, log and version.

        The explicit inputs override paths in the configuration. An empty dataset
        is rejected to prevent Sage from using configuration inputs instead.
        Relative configuration references resolve beside the configuration file.
        Sage errors propagate as ``subprocess.CalledProcessError``; files already
        written remain available for inspection. Existing output directories are
        never reused. Database format labels and file extensions are not checked.
        """
        if not dataset.files:
            raise ValueError("SageWorkflow requires at least one measurement file.")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        configuration = self.configuration.resolve()
        self._execute(
            [str(self.executable.resolve()), "--version"],
            output_dir / "version.txt",
            configuration.parent,
        )
        self._execute(
            self._command(dataset, database, output_dir),
            output_dir / "sage.log",
            configuration.parent,
        )
        return WorkflowResult(
            format="sage",
            files={
                str(path.relative_to(output_dir)): path
                for path in sorted(output_dir.rglob("*"))
                if path.is_file()
            },
        )

    def _command(
        self, dataset: Dataset, database: Database, output_dir: Path
    ) -> list[str]:
        return [
            str(self.executable.resolve()),
            str(self.configuration.resolve()),
            "--disable-telemetry-i-dont-want-to-improve-sage",
            "--fasta",
            str(database.path.resolve()),
            "--output_directory",
            str(output_dir),
            *[str(path.resolve()) for path in dataset.files],
        ]

    def _execute(self, command: list[str], log_path: Path, cwd: Path) -> None:
        with log_path.open("w") as log:
            subprocess.run(
                command,
                cwd=cwd,
                env={**os.environ, "RAYON_NUM_THREADS": str(self.threads)},
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
