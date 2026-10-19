"""Launch the existing CLI and inspect its files without a UI dependency."""

import codecs
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from interop_trace.experiments import load_experiments


@dataclass(frozen=True)
class SavedRun:
    """One output directory, its recorded experiments and execution status."""

    directory: Path
    status: str
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

    def start(self, ids: Sequence[str]) -> Path:
        """Validate, then launch a single CLI process with a durable console log."""
        with self._lock:
            if self.active:
                raise RuntimeError("A run is already active in this interface.")
            source = self.directory / "experiments"
            load_experiments(source, ids)
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
                        *ids,
                        "--directory",
                        str(source),
                        "--output",
                        str(output),
                    ],
                    cwd=self.directory,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                )
            self._processes[output] = process
            return output

    def history(self) -> list[SavedRun]:
        """Include CLI runs and launches that failed before creating a snapshot."""
        results = self.directory / "results"
        directories = {path.parent for path in results.glob("*/configuration.json")}
        directories.update(
            path.with_name(path.name.removesuffix(".console.log"))
            for path in results.glob("ui-*.console.log")
        )
        directories.update(self._processes)
        return [
            self._read(path)
            for path in sorted(directories, key=_modified, reverse=True)
        ]

    def _read(self, directory: Path) -> SavedRun:
        configuration = read_record(directory / "configuration.json")
        experiments = []
        choices = configuration.get("experiments", [])
        for choice in choices if isinstance(choices, list) else []:
            if not isinstance(choice, dict):
                continue
            name = choice.get("id")
            if (
                not isinstance(name, str)
                or not name
                or name in {".", ".."}
                or Path(name).name != name
            ):
                continue
            record = read_record(directory / name / "experiment.json")
            experiments.append(
                {**record, "id": name}
                if record
                else {"id": name, "status": "not_started"}
            )
        process = self._processes.get(directory)
        code = process.poll() if process is not None else None
        if (code is not None and code != 0) or any(
            record.get("status") == "failed" for record in experiments
        ):
            status = "failed"
        elif experiments and all(r.get("status") == "completed" for r in experiments):
            status = "completed"
        elif process is not None and code is None:
            status = "running"
        else:
            status = "unknown"
        return SavedRun(directory, status, tuple(experiments))


def read_record(path: Path) -> dict[str, Any]:
    """Tolerate missing or partially written records; the next poll retries."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


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
