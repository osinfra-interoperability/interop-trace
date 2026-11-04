"""Post-run failure assessment, separate from execution and benchmarking."""

import json
from pathlib import Path

from interop_trace.experiments.records import experiment_rows, save_table
from interop_trace.status import AssessmentCategory, AssessmentOutcome, ExecutionStatus


def assess_experiment(directory: Path) -> Path:
    """Save an unknown assessment for a finished experiment.

    Classification is currently a placeholder: no cause is inferred and no logs
    are interpreted. Existing assessments are preserved rather than overwritten.
    """
    directory = directory.resolve()
    record = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("status") != ExecutionStatus.FINISHED:
        raise ValueError("Select a finished experiment.")
    assessment: dict[str, object] = {
        "source": "experiment.json",
        "method": "placeholder",
        "outcome": AssessmentOutcome.UNKNOWN,
        "category": AssessmentCategory.UNKNOWN,
        "cause": None,
        "evidence": [],
    }
    output = directory / "classification.json"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(assessment, indent=2) + "\n")
    save_table(directory.parent)
    return output


def assess_run(directory: Path) -> list[Path]:
    """Assess finished experiments in a run, preserving existing assessments."""
    return [
        assess_experiment(directory / row["id"])
        for row in experiment_rows(directory)
        if row["status"] == ExecutionStatus.FINISHED
        and not (directory / row["id"] / "classification.json").exists()
    ]
