"""Launch the existing CLI and inspect its files without a UI dependency."""

import codecs
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from interop_trace.downloads import DEFAULT_CACHE_DIR
from interop_trace.experiments import create_run, load_experiments
from interop_trace.experiments.records import experiment_rows, read_record
from interop_trace.status import ExecutionStatus


@dataclass(frozen=True)
class SavedRun:
    """One output directory, its recorded experiments and execution status."""

    directory: Path
    status: ExecutionStatus | None
    experiments: tuple[dict[str, Any], ...]


class RunBrowser:
    """One local UI server's launcher; history comes from existing run files."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self._processes: dict[Path, subprocess.Popen[bytes]] = {}
        self._lock = Lock()

    @property
    def active(self) -> bool:
        return any(
            process.poll() is None for process in tuple(self._processes.values())
        )

    def create(self, name: str, ids: Sequence[str]) -> Path:
        """Create a named run and its initial files without starting any process."""
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", name):
            raise ValueError(
                "Run names must start with a letter or digit and contain only "
                "letters, digits, dots, underscores or hyphens."
            )
        configuration = load_experiments(self.directory / "experiments", ids)
        return create_run(
            configuration,
            output_dir=self.directory / "results" / name,
            cache_dir=self.directory / DEFAULT_CACHE_DIR,
        )

    def start(self, directory: Path) -> Path:
        """Execute a created run in one CLI process with a durable console log."""
        with self._lock:
            if self.active:
                raise RuntimeError("A run is already active in this interface.")
            directory = directory.resolve()
            rows = experiment_rows(directory)
            if (
                directory.parent != (self.directory / "results").resolve()
                or not rows
                or (directory / "execution.json").exists()
                or any(r["status"] != ExecutionStatus.NOT_STARTED for r in rows)
            ):
                raise ValueError("Select a created run that has not started.")
            with console_log(directory).open("ab") as stream:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "interop_trace",
                        "execute",
                        str(directory),
                    ],
                    cwd=self.directory,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                )
            self._processes[directory] = process
            return directory

    def history(self) -> list[SavedRun]:
        """List created runs, including executions started through the CLI."""
        results = self.directory / "results"
        directories = {path.parent for path in results.glob("*/configuration.json")}
        directories.update(self._processes)
        return [
            self._read(path)
            for path in sorted(directories, key=_modified, reverse=True)
        ]

    def _read(self, directory: Path) -> SavedRun:
        experiments = experiment_rows(directory)
        process = self._processes.get(directory)
        code = process.poll() if process is not None else None
        status = None
        if process is not None:
            status = (
                ExecutionStatus.RUNNING if code is None else ExecutionStatus.FINISHED
            )
        elif (
            read_record(directory / "execution.json").get("status")
            == ExecutionStatus.FINISHED
        ) or (
            experiments
            and all(r.get("status") == ExecutionStatus.FINISHED for r in experiments)
        ):
            status = ExecutionStatus.FINISHED
        elif (
            experiments
            and not (directory / "execution.json").exists()
            and all(r["status"] == ExecutionStatus.NOT_STARTED for r in experiments)
        ):
            status = ExecutionStatus.NOT_STARTED
        return SavedRun(directory, status, tuple(experiments))


def console_log(directory: Path) -> Path:
    return directory.with_name(directory.name + ".console.log")


def file_preview(path: Path, limit: int = 32_768) -> str:
    """Read a bounded text preview without rendering binary outputs."""
    if path.suffix.lower() == ".log":
        return log_tail(path, limit)
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError:
        return "File not available."
    if b"\x00" in data:
        return "Binary file: use Download file to inspect it."
    truncated = len(data) > limit
    try:
        text = codecs.getincrementaldecoder("utf-8")().decode(
            data[:limit], final=not truncated
        )
    except UnicodeDecodeError:
        return "Binary or non-UTF-8 file: use Download file to inspect it."
    if truncated:
        text += "\n\n[Preview truncated; download the complete file.]"
    return text or "Empty file."


def log_tail(path: Path, limit: int = 32_768) -> str:
    """Read a bounded UTF-8 preview even while a process appends to the file."""
    try:
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - limit))
            return stream.read(limit).decode("utf-8", errors="replace")
    except OSError:
        return "Log not available yet."


def _modified(directory: Path) -> float:
    for path in (directory, console_log(directory)):
        try:
            return path.stat().st_mtime
        except OSError:
            continue
    return 0.0
