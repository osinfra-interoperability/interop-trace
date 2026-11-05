"""Post-run failure assessment, separate from execution and benchmarking."""

import json
import math
from pathlib import Path
from typing import Any

from interop_trace.experiments.records import experiment_rows, save_table
from interop_trace.status import AssessmentCategory, AssessmentOutcome, ExecutionStatus

_ERROR_CATEGORIES = {
    "UnsupportedFormatError": AssessmentCategory.UNSUPPORTED_FORMAT,
    "MissingOutputError": AssessmentCategory.MISSING_OUTPUT,
    "ResultSchemaError": AssessmentCategory.SCHEMA_MISMATCH,
    "UnsupportedEvaluationError": AssessmentCategory.UNSUPPORTED_EVALUATION,
    "BenchmarkInputMismatchError": AssessmentCategory.BENCHMARK_INPUT_MISMATCH,
    "FileNotFoundError": AssessmentCategory.MISSING_FILE,
    "NotADirectoryError": AssessmentCategory.FILESYSTEM,
    "IsADirectoryError": AssessmentCategory.FILESYSTEM,
    "MemoryError": AssessmentCategory.RESOURCE_LIMIT,
    "TimeoutError": AssessmentCategory.TIMEOUT,
    "TimeoutExpired": AssessmentCategory.TIMEOUT,
    "Timeout": AssessmentCategory.TIMEOUT,
    "ConnectTimeout": AssessmentCategory.TIMEOUT,
    "ReadTimeout": AssessmentCategory.TIMEOUT,
    "ConnectionError": AssessmentCategory.NETWORK,
    "ConnectionRefusedError": AssessmentCategory.NETWORK,
    "ConnectionResetError": AssessmentCategory.NETWORK,
    "ConnectionAbortedError": AssessmentCategory.NETWORK,
    "ProxyError": AssessmentCategory.NETWORK,
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
    "ETIMEDOUT": AssessmentCategory.TIMEOUT,
    "ENETDOWN": AssessmentCategory.NETWORK,
    "ENETUNREACH": AssessmentCategory.NETWORK,
    "EHOSTUNREACH": AssessmentCategory.NETWORK,
    "ECONNREFUSED": AssessmentCategory.NETWORK,
    "ECONNRESET": AssessmentCategory.NETWORK,
    "ECONNABORTED": AssessmentCategory.NETWORK,
}


def assess_experiment(directory: Path) -> Path:
    """Assess a finished experiment using saved errors and acceptance criteria.

    Logs are not interpreted. Existing assessments are preserved rather than
    overwritten; execution without an error does not imply scientific success.
    """
    directory = directory.resolve()
    record = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    if not isinstance(record, dict) or record.get("status") != ExecutionStatus.FINISHED:
        raise ValueError("Select a finished experiment.")
    assessment = {
        **_assess(record),
        "diagnosis": _diagnose(directory, record),
    }
    output = directory / "classification.json"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(assessment, indent=2) + "\n")
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
    assessment: dict[str, object] = {
        "source": "experiment.json",
        "rule": rule,
        "outcome": outcome,
        "category": category,
        "detected_stage": record.get("stage") if error else None,
        "evidence": evidence,
    }
    if not error and record.get("acceptance"):
        assessment.update(_check_acceptance(record))
    return assessment


def _check_acceptance(record: dict[str, Any]) -> dict[str, object]:
    metrics = record.get("evaluation", {}).get("metrics", {})
    checks = {}
    for metric, limits in record["acceptance"].items():
        value = metrics.get(metric)
        outcome = AssessmentOutcome.UNKNOWN
        if type(value) in {int, float} and math.isfinite(value):
            outcome = (
                AssessmentOutcome.SUCCESS
                if limits.get("min", -math.inf) <= value <= limits.get("max", math.inf)
                else AssessmentOutcome.FAILURE
            )
        else:
            value = None
        checks[metric] = {**limits, "value": value, "outcome": outcome}
    outcomes = {check["outcome"] for check in checks.values()}
    if AssessmentOutcome.FAILURE in outcomes:
        outcome = AssessmentOutcome.FAILURE
        rule = "acceptance_not_met"
        category = AssessmentCategory.ACCEPTANCE_CRITERION_NOT_MET
    elif AssessmentOutcome.UNKNOWN in outcomes:
        outcome, rule, category = (
            AssessmentOutcome.UNKNOWN,
            "acceptance_unavailable",
            AssessmentCategory.UNKNOWN,
        )
    else:
        outcome, rule, category = AssessmentOutcome.SUCCESS, "acceptance_met", None
    return {
        "outcome": outcome,
        "category": category,
        "rule": rule,
        "detected_stage": "assessment"
        if outcome == AssessmentOutcome.FAILURE
        else None,
        "checks": checks,
        "evidence": ["acceptance", "evaluation.metrics"],
    }


def _diagnose(directory: Path, record: dict[str, Any]) -> dict[str, object]:
    """Placeholder for diagnosis using the saved record and experiment files.

    A future diagnostic method, such as an LLM, can use these inputs. For now,
    no cause or originating stage is inferred and no external calls are made.
    """
    return {"method": "placeholder", "origin_stage": None, "evidence": []}


def assess_run(directory: Path) -> list[Path]:
    """Assess finished experiments in a run, preserving existing assessments."""
    return [
        assess_experiment(directory / row["id"])
        for row in experiment_rows(directory)
        if row["status"] == ExecutionStatus.FINISHED
        and not (directory / row["id"] / "classification.json").exists()
    ]
