"""Execute explicit experiments sequentially through the component contracts."""

import json
import platform
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from interop_trace import __version__
from interop_trace.components import RequiresSetup
from interop_trace.downloads import DEFAULT_CACHE_DIR, DownloadCache
from interop_trace.evaluation import EvaluationResult
from interop_trace.experiments.config import Experiment, RunConfiguration, load_snapshot
from interop_trace.experiments.records import read_record, save_table
from interop_trace.status import ExecutionStatus


@dataclass(frozen=True)
class RunResult:
    """Returned evaluations and recorded errors, keyed by experiment ID."""

    completed: dict[str, EvaluationResult]
    failed: dict[str, str]


def run_experiments(
    configuration: RunConfiguration,
    *,
    output_dir: Path,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> RunResult:
    """Create and execute a run, continuing after ordinary experiment errors."""
    create_run(configuration, output_dir=output_dir, cache_dir=cache_dir)
    return execute_run(output_dir)


def create_run(
    configuration: RunConfiguration,
    *,
    output_dir: Path,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Save selected YAML, initial records and a table without setup or downloads."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    _write(
        output_dir / "configuration.json",
        {
            **configuration.snapshot,
            "interop_trace_version": __version__,
            "cache": str(cache_dir.resolve()),
            "name": output_dir.name,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    for experiment in configuration.experiments:
        folder = output_dir / experiment.id
        folder.mkdir()
        _write(
            folder / "experiment.json",
            {
                "id": experiment.id,
                "status": ExecutionStatus.NOT_STARTED,
            },
        )
    save_table(output_dir)
    return output_dir


def execute_run(output_dir: Path) -> RunResult:
    """Execute a created run once, using its saved YAML and recording the platform."""
    output_dir = output_dir.resolve()
    snapshot = read_record(output_dir / "configuration.json")
    configuration = load_snapshot(snapshot)
    if any(
        read_record(output_dir / e.id / "experiment.json").get("status")
        != ExecutionStatus.NOT_STARTED
        for e in configuration.experiments
    ):
        raise ValueError(
            "This run has already started; create a new run to execute again."
        )
    (output_dir / "execution.json").touch(exist_ok=False)
    with _status(output_dir / "execution.json", {}):
        _write(output_dir / "environment.json", _environment())
        return _execute(
            configuration, output_dir, DownloadCache(Path(snapshot["cache"]))
        )


def _execute(
    configuration: RunConfiguration, output_dir: Path, cache: DownloadCache
) -> RunResult:
    completed: dict[str, EvaluationResult] = {}
    failed: dict[str, str] = {}
    for experiment in configuration.experiments:
        try:
            completed[experiment.id] = _run_experiment(
                experiment, output_dir / experiment.id, cache
            )
        except Exception as error:
            failed[experiment.id] = f"{type(error).__name__}: {error}"
    _write(
        output_dir / "summary.json",
        {"completed": list(completed), "failed": failed},
    )
    return RunResult(completed, failed)


def _environment() -> dict[str, str]:
    """Describe the runner's environment, not its external tools or runtimes."""
    return {
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }


def _run_experiment(
    experiment: Experiment, directory: Path, cache: DownloadCache
) -> EvaluationResult:
    path = directory / "experiment.json"
    record: dict[str, Any] = {
        "id": experiment.id,
        "stage": "setup",
    }
    with _status(path, record):
        for role, component in (
            ("dataset", experiment.dataset),
            ("database", experiment.database),
            ("workflow", experiment.workflow),
            ("benchmark", experiment.benchmark),
        ):
            _stage(path, record, f"setup:{role}")
            if isinstance(component, RequiresSetup):
                component.setup(cache=cache)
        _stage(path, record, "dataset")
        dataset = experiment.dataset.prepare(output_dir=directory / "dataset")
        record["dataset"] = asdict(dataset)
        _stage(path, record, "database")
        database = experiment.database.prepare(output_dir=directory / "database")
        record["database"] = asdict(database)
        _stage(path, record, "workflow")
        result = experiment.workflow.run(
            dataset, database, output_dir=directory / "workflow"
        )
        record["workflow"] = asdict(result)
        _stage(path, record, "evaluation")
        evaluation = experiment.benchmark.evaluate(
            result, dataset, database, output_dir=directory / "evaluation"
        )
        record["evaluation"] = asdict(evaluation)
    return evaluation


def _stage(path: Path, record: dict[str, Any], name: str) -> None:
    record["stage"] = name
    _write(path, record)
    save_table(path.parent.parent)


@contextmanager
def _status(path: Path, record: dict[str, Any]) -> Iterator[None]:
    record.update(
        status=ExecutionStatus.RUNNING, started_at=datetime.now(UTC).isoformat()
    )
    _write(path, record)
    try:
        yield
    except BaseException as error:
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        record.update(
            status=ExecutionStatus.FINISHED, finished_at=datetime.now(UTC).isoformat()
        )
        _write(path, record)
        if path.name == "experiment.json":
            save_table(path.parent.parent)


def _write(path: Path, record: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(record, default=str, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
