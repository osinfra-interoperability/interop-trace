"""Read execution evidence and export the experiment table shared by interfaces."""

import csv
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

TABLE_FIELDS = (
    "id",
    "dataset",
    "database",
    "workflow",
    "benchmark",
    "prediction_conclusion",
    "prediction_coverage",
    "technical_prediction",
    "technical_coverage",
    "semantic_prediction",
    "semantic_coverage",
    "host_prediction",
    "host_coverage",
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
        prediction = read_record(folder / "prediction.json")
        aspects = prediction.get("aspects", {})
        # Earlier technical summaries combined formats and host OS checks.
        technical = aspects.get("technical", {}) if "host" in aspects else {}
        semantic = aspects.get("semantic", {})
        host = aspects.get("host", {})
        rows.append(
            {
                **{field: choice.get(field, "") for field in TABLE_FIELDS},
                "prediction_conclusion": prediction.get("conclusion", ""),
                "prediction_coverage": _coverage(prediction),
                "technical_prediction": technical.get("conclusion", ""),
                "technical_coverage": _coverage(technical),
                "semantic_prediction": semantic.get("conclusion", ""),
                "semantic_coverage": _coverage(semantic),
                "host_prediction": host.get("conclusion", ""),
                "host_coverage": _coverage(host),
                "status": record.get("status"),
                "stage": record.get("stage", ""),
                "error": record.get("error", {}).get("type", ""),
                "assessment_outcome": assessment.get("outcome", ""),
                "assessment_category": assessment.get("category") or "",
            }
        )
    return rows


def _coverage(summary: dict[str, Any]) -> str:
    value = summary.get("evidence_coverage")
    return "" if value is None else str(value)


def save_table(directory: Path) -> None:
    """Save the same rows shown in the UI; source JSON records remain authoritative."""
    if not (directory / "configuration.json").is_file():
        return
    with NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=directory.parent, delete=False
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=TABLE_FIELDS)
        writer.writeheader()
        writer.writerows(experiment_rows(directory))
    Path(stream.name).replace(directory / "experiments.csv")
