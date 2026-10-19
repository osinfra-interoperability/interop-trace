"""Run a pinned Comet release with native search parameters."""

import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.downloads import DownloadCache
from interop_trace.workflows._execution import (
    measurement_files,
    run_command,
    workflow_result,
)
from interop_trace.workflows.base import WorkflowResult
from interop_trace.workflows.registry import registry


@registry.register(
    "comet",
    summary="Local Comet peptide identification",
    documentation="components.md#comet",
    paths=("configuration", "executable"),
)
@dataclass
class CometWorkflow:
    """Native Comet parameters, with automatic installation or a local executable."""

    configuration: Path
    executable: Path | None = None
    version: str = "2026.03.0"
    _executable: Path | None = field(default=None, init=False, repr=False)

    def setup(self, *, cache: DownloadCache) -> None:
        """Resolve a local executable or cache the platform's published binary."""
        self._executable = None
        if self.executable is not None:
            executable = self.executable.resolve()
        else:
            system, machine = platform.system(), platform.machine().lower()
            targets = {
                ("Darwin", "arm64"): "aarch64.macos",
                ("Darwin", "x86_64"): "macos",
                ("Linux", "aarch64"): "aarch64.linux",
                ("Linux", "x86_64"): "linux",
                ("Windows", "amd64"): "win64",
            }
            try:
                target = targets[system, machine]
            except KeyError:
                raise ValueError(f"No Comet download for {system}/{machine}.") from None
            url = (
                "https://github.com/UWPR/Comet/releases/download/"
                f"v{self.version}/comet.{target}.exe"
            )
            executable = cache.fetch(
                url,
                name="comet",
                kind="workflow",
                filename="comet.exe",
                metadata={"version": self.version},
            ).path
            executable.chmod(executable.stat().st_mode | 0o111)
        if not executable.is_file():
            raise FileNotFoundError(executable)
        self._executable = executable

    def run(
        self, dataset: Dataset, database: Database, *, output_dir: Path
    ) -> WorkflowResult:
        """Search each measurement separately, keeping native files and logs."""
        if self._executable is None:
            raise RuntimeError("Call CometWorkflow.setup(cache=...) before run().")
        files = measurement_files(dataset)
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        settings = output_dir / "comet.params"
        shutil.copyfile(self.configuration, settings)
        for index, source in enumerate(files, 1):
            base = output_dir / f"{index:03}.comet"
            run_command(
                [
                    str(self._executable),
                    f"-P{settings}",
                    f"-D{database.path.resolve()}",
                    f"-N{base}",
                    str(source),
                ],
                base.with_suffix(".comet.log"),
                self.configuration.resolve().parent,
            )
        return workflow_result("comet", output_dir)
