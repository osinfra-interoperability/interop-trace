"""Execute explicit experiments sequentially through the component contracts."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from interop_trace import __version__
from interop_trace.components import RequiresSetup
from interop_trace.downloads import DEFAULT_CACHE_DIR, DownloadCache
from interop_trace.evaluation import EvaluationResult
from interop_trace.experiments.config import Experiment, RunConfiguration


def run_experiments(
    configuration: RunConfiguration,
    *,
    output_dir: Path,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> tuple[EvaluationResult, ...]:
    """Run each experiment in a new directory, stopping on the first failure.

    Preserve the loaded YAML contents and selected settings before setup. A failed
    experiment retains its reports, logs and failed-stage record; later experiments
    are not started. Downloads share a cache, but workflow results are not reused.
    """
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    cache = DownloadCache(cache_dir)
    _write(
        output_dir / "configuration.json",
        {
            **configuration.snapshot,
            "interop_trace_version": __version__,
            "cache": str(cache.root),
            "experiments": [
                {"id": experiment.id, **experiment.settings}
                for experiment in configuration.experiments
            ],
        },
    )
    record: dict[str, Any] = {
        "experiments": {
            experiment.id: "not_started" for experiment in configuration.experiments
        }
    }
    results = []
    with _status(output_dir / "run.json", record):
        for experiment in configuration.experiments:
            record["experiments"][experiment.id] = "running"
            _write(output_dir / "run.json", record)
            try:
                results.append(
                    _run_experiment(experiment, output_dir / experiment.id, cache)
                )
            except BaseException:
                record["experiments"][experiment.id] = "failed"
                raise
            record["experiments"][experiment.id] = "completed"
    return tuple(results)


def _run_experiment(
    experiment: Experiment, directory: Path, cache: DownloadCache
) -> EvaluationResult:
    directory.mkdir()
    path = directory / "experiment.json"
    record: dict[str, Any] = {
        "id": experiment.id,
        "settings": experiment.settings,
        "stage": "setup",
    }
    with _status(path, record):
        for role in ("dataset", "database", "workflow", "benchmark"):
            _stage(path, record, f"setup:{role}")
            component = getattr(experiment, role)
            if isinstance(component, RequiresSetup):
                component.setup(cache=cache)
        evaluation = _execute(experiment, directory, record)
    return evaluation


def _execute(
    experiment: Experiment, directory: Path, record: dict[str, Any]
) -> EvaluationResult:
    path = directory / "experiment.json"
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


@contextmanager
def _status(path: Path, record: dict[str, Any]) -> Iterator[None]:
    record.update(status="running", started_at=datetime.now(UTC).isoformat())
    _write(path, record)
    try:
        yield
    except BaseException as error:
        record.update(
            status="failed", error={"type": type(error).__name__, "message": str(error)}
        )
        raise
    else:
        record["status"] = "completed"
    finally:
        record["finished_at"] = datetime.now(UTC).isoformat()
        _write(path, record)


def _write(path: Path, record: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(record, default=str, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )
