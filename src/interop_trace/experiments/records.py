"""Read execution evidence and export the experiment table shared by interfaces."""

import csv
import json
from pathlib import Path
from typing import Any

from interop_trace.status import ExecutionStatus

TABLE_FIELDS = (
    "id",
    "dataset",
    "database",
    "workflow",
    "benchmark",
    "status",
    "stage",
    "error",
    "assessment_outcome",
    "assessment_category",
)


def read_record(path: Path) -> dict[str, Any]:
    """Tolerate missing or partially written records while a run is progressing."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def experiment_rows(directory: Path) -> list[dict[str, Any]]:
    """Project saved choices, execution records and stage assessments into rows."""
    rows = []
    for choice in read_record(directory / "configuration.json").get("experiments", []):
        name = choice["id"]
        if not name or Path(name).name != name or name in {".", ".."}:
            continue
        folder = directory / name
        record = read_record(folder / "experiment.json")
        assessment = read_record(folder / "classification.json")
        rows.append(
            {
                **{field: choice.get(field, "") for field in TABLE_FIELDS},
                "status": record.get("status", ExecutionStatus.NOT_STARTED),
                "stage": record.get("stage", ""),
                "error": record.get("error", {}).get("type", ""),
                "assessment_outcome": assessment.get("outcome", ""),
                "assessment_category": assessment.get("category", ""),
            }
        )
    return rows


def save_table(directory: Path) -> None:
    """Save the same rows shown in the UI; source JSON records remain authoritative."""
    if not (directory / "configuration.json").is_file():
        return
    with (directory / "experiments.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=TABLE_FIELDS)
        writer.writeheader()
        writer.writerows(experiment_rows(directory))
