"""Post-run failure assessment, separate from execution and benchmarking."""

import json
from pathlib import Path

from interop_trace.status import AssessmentCategory, AssessmentOutcome, ExecutionStatus


def classify_failure(directory: Path) -> Path:
    """Save an unknown assessment for a finished experiment with a recorded error.

    Classification is currently a placeholder: no cause is inferred and no logs
    are interpreted. Existing assessments are preserved rather than overwritten.
    """
    directory = directory.resolve()
    record = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    if (
        not isinstance(record, dict)
        or record.get("status") != ExecutionStatus.FINISHED
        or not record.get("error")
    ):
        raise ValueError("Select a finished experiment with a recorded error.")
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
    return output
