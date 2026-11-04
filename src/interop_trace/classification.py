"""Post-run failure assessment, separate from execution and benchmarking."""

import json
from pathlib import Path

from interop_trace.status import ExecutionStatus


def classify_failure(directory: Path) -> Path:
    """Save an unknown assessment for a failed experiment without changing it.

    Classification is currently a placeholder: no cause is inferred and no logs
    are interpreted. Existing assessments are preserved rather than overwritten.
    """
    directory = directory.resolve()
    record = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("status") != ExecutionStatus.FAILED:
        raise ValueError("Select a failed experiment directory.")
    assessment: dict[str, object] = {
        "source": "experiment.json",
        "method": "placeholder",
        "category": "unknown",
        "cause": None,
        "evidence": [],
    }
    output = directory / "classification.json"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(assessment, indent=2) + "\n")
    return output
