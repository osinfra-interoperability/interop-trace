"""Small helpers shared by local command-line workflows."""

import json
import os
import subprocess
from pathlib import Path

import pooch

from interop_trace.datasets import Dataset
from interop_trace.workflows.base import WorkflowResult


def run_command(
    command: list[str],
    log: Path,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> None:
    """Save the invocation before execution, keeping output even on failure."""
    overrides = environment or {}
    log.with_suffix(".command.json").write_text(
        json.dumps(
            {"command": command, "cwd": str(cwd), "environment": overrides}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    with log.open("w") as stream:
        subprocess.run(
            command,
            cwd=cwd,
            env={**os.environ, **overrides},
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
        )


def measurement_files(dataset: Dataset) -> tuple[Path, ...]:
    """Reuse gzip decompression beside cached inputs, preserving their names."""
    if not dataset.files:
        raise ValueError("Workflow requires at least one measurement file.")
    files = []
    for source in dataset.files:
        source = source.resolve()
        if source.suffix.lower() == ".gz":
            destination = source.with_suffix("")
            try:
                pooch.Decompress(method="gzip", name=destination.name)(
                    str(source), "fetch", None
                )
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
            source = destination
        files.append(source)
    return tuple(files)


def workflow_result(format: str, directory: Path) -> WorkflowResult:
    """Collect native outputs and the invocation records without converting them."""
    return WorkflowResult(
        format,
        {
            str(path.relative_to(directory)): path
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        },
    )
