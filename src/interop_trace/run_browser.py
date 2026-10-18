"""Launch the existing CLI and inspect its files without a UI dependency."""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from interop_trace.experiments import load_configuration


@dataclass(frozen=True)
class SavedRun:
    """One output directory, its recorded experiments and execution status."""

    directory: Path
    status: str
    configuration: dict[str, Any]
    experiments: tuple[dict[str, Any], ...]


class RunBrowser:
    """One local UI server's launcher; history comes from existing run files."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self.output: Path | None = None
        self.process: subprocess.Popen[bytes] | None = None
        self._lock = Lock()

    @property
    def active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def configurations(self) -> list[Path]:
        """Find checked-in run configurations without constructing components."""
        source = self.directory / "experiments/runs"
        return sorted({*source.rglob("*.yaml"), *source.rglob("*.yml")})

    def start(self, configuration: Path) -> Path:
        """Validate, then launch a single CLI process with a durable console log."""
        with self._lock:
            if self.active:
                raise RuntimeError("A run is already active in this interface.")
            configuration = configuration.resolve()
            if configuration not in self.configurations():
                raise ValueError("Choose a configuration from experiments/runs/.")
            load_configuration(configuration)
            name = (
                datetime.now(UTC).strftime("ui-%Y%m%dT%H%M%S") + f"-{uuid4().hex[:8]}"
            )
            output = self.directory / "results" / name
            output.parent.mkdir(parents=True, exist_ok=True)
            with console_log(output).open("xb") as stream:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "interop_trace",
                        "run",
                        str(configuration),
                        "--output",
                        str(output),
                    ],
                    cwd=self.directory,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                )
            self.output, self.process = output, process
            return output

    def history(self) -> list[SavedRun]:
        """Include CLI runs and launches that failed before creating a snapshot."""
        results = self.directory / "results"
        directories = {path.parent for path in results.glob("*/configuration.json")}
        directories.update(
            path.with_name(path.name.removesuffix(".console.log"))
            for path in results.glob("ui-*.console.log")
        )
        if self.output is not None:
            directories.add(self.output)
        return [self._read(path) for path in sorted(directories, reverse=True)]

    def _read(self, directory: Path) -> SavedRun:
        configuration = read_record(directory / "configuration.json")
        experiments = []
        for choice in configuration.get("experiments", []):
            if not isinstance(choice, dict):
                continue
            name = choice.get("id")
            if not isinstance(name, str) or not name or Path(name).name != name:
                continue
            record = read_record(directory / name / "experiment.json")
            experiments.append(record or {"id": name, "status": "not_started"})
        code = (
            self.process.poll() if self.process and directory == self.output else None
        )
        if (code is not None and code != 0) or any(
            record.get("status") == "failed" for record in experiments
        ):
            status = "failed"
        elif experiments and all(r.get("status") == "completed" for r in experiments):
            status = "completed"
        elif directory == self.output and self.active:
            status = "running"
        else:
            status = "unknown"
        return SavedRun(directory, status, configuration, tuple(experiments))


def read_record(path: Path) -> dict[str, Any]:
    """Tolerate missing or partially written records; the next poll retries."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def console_log(directory: Path) -> Path:
    return directory.with_name(directory.name + ".console.log")


def log_tail(path: Path, limit: int = 32_768) -> str:
    """Read a bounded UTF-8 preview even while a process appends to the file."""
    try:
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - limit))
            return stream.read(limit).decode("utf-8", errors="replace")
    except OSError:
        return "Log not available yet."
