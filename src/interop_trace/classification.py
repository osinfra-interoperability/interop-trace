"""Post-run failure assessment, separate from execution and benchmarking."""

import json
from pathlib import Path
from typing import Any

from interop_trace.experiments.records import experiment_rows, save_table
from interop_trace.status import AssessmentCategory, AssessmentOutcome, ExecutionStatus

_ERROR_CATEGORIES = {
    "FileNotFoundError": AssessmentCategory.MISSING_FILE,
    "NotADirectoryError": AssessmentCategory.FILESYSTEM,
    "IsADirectoryError": AssessmentCategory.FILESYSTEM,
    "MemoryError": AssessmentCategory.RESOURCE_LIMIT,
}
_ERRNO_CATEGORIES = {
    "ENOENT": AssessmentCategory.MISSING_FILE,
    "ENOTDIR": AssessmentCategory.FILESYSTEM,
    "EISDIR": AssessmentCategory.FILESYSTEM,
    "EROFS": AssessmentCategory.FILESYSTEM,
    "ENOSPC": AssessmentCategory.RESOURCE_LIMIT,
    "EDQUOT": AssessmentCategory.RESOURCE_LIMIT,
    "ENOMEM": AssessmentCategory.RESOURCE_LIMIT,
    "EMFILE": AssessmentCategory.RESOURCE_LIMIT,
    "ENFILE": AssessmentCategory.RESOURCE_LIMIT,
}


def assess_experiment(directory: Path) -> Path:
    """Assess a finished experiment using deterministic error rules.

    Logs are not interpreted. Existing assessments are preserved rather than
    overwritten; execution without an error does not imply scientific success.
    """
    directory = directory.resolve()
    record = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("status") != ExecutionStatus.FINISHED:
        raise ValueError("Select a finished experiment.")
    output = directory / "classification.json"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(_assess(record), indent=2) + "\n")
    save_table(directory.parent)
    return output


def _assess(record: dict[str, Any]) -> dict[str, object]:
    error = record.get("error")
    outcome = AssessmentOutcome.UNKNOWN
    category = AssessmentCategory.UNKNOWN
    rule = "no_recorded_error"
    evidence = []
    if error:
        outcome = AssessmentOutcome.FAILURE
        rule, evidence = "unclassified_error", ["error"]
        if error.get("type") in {"KeyboardInterrupt", "SystemExit"}:
            outcome = AssessmentOutcome.UNKNOWN
            rule, evidence = "execution_interrupted", ["error.type"]
        elif error.get("type") == "PermissionError":
            category = AssessmentCategory.PERMISSION
            rule, evidence = "permission_error", ["error.type"]
        elif error.get("errno_name") in {"EBADARCH", "ENOEXEC"}:
            category = AssessmentCategory.ENVIRONMENT
            rule, evidence = "executable_launch_error", ["error.errno_name"]
        elif error.get("type") == "CalledProcessError":
            category = AssessmentCategory.PROCESS_ERROR
            rule, evidence = "process_nonzero_exit", ["error.type", "error.returncode"]
        elif error.get("type") in _ERROR_CATEGORIES:
            category = _ERROR_CATEGORIES[error["type"]]
            rule, evidence = f"{category}_error", ["error.type"]
        elif error.get("errno_name") in _ERRNO_CATEGORIES:
            category = _ERRNO_CATEGORIES[error["errno_name"]]
            rule, evidence = f"{category}_error", ["error.errno_name"]
    return {
        "source": "experiment.json",
        "method": "deterministic",
        "rule": rule,
        "outcome": outcome,
        "category": category,
        "evidence": evidence,
    }


def assess_run(directory: Path) -> list[Path]:
    """Assess finished experiments in a run, preserving existing assessments."""
    return [
        assess_experiment(directory / row["id"])
        for row in experiment_rows(directory)
        if row["status"] == ExecutionStatus.FINISHED
        and not (directory / row["id"] / "classification.json").exists()
    ]
