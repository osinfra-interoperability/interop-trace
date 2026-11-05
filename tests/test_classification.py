"""Exercise post-run assessment through the CLI without classification services."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from interop_trace.interfaces.cli import app


@pytest.mark.parametrize(
    "error,expected",
    [
        (None, ("unknown", "unknown", "no_recorded_error", [])),
        (
            {"type": "UnsupportedFormatError"},
            (
                "failure",
                "unsupported_format",
                "unsupported_format_error",
                ["error.type"],
            ),
        ),
        (
            {"type": "MissingOutputError"},
            ("failure", "missing_output", "missing_output_error", ["error.type"]),
        ),
        (
            {"type": "ResultSchemaError"},
            ("failure", "schema_mismatch", "schema_mismatch_error", ["error.type"]),
        ),
        (
            {"type": "UnsupportedEvaluationError"},
            (
                "failure",
                "unsupported_evaluation",
                "unsupported_evaluation_error",
                ["error.type"],
            ),
        ),
        (
            {"type": "BenchmarkInputMismatchError"},
            (
                "failure",
                "benchmark_input_mismatch",
                "benchmark_input_mismatch_error",
                ["error.type"],
            ),
        ),
        (
            {"type": "KeyboardInterrupt"},
            ("unknown", "unknown", "execution_interrupted", ["error.type"]),
        ),
        (
            {"type": "SystemExit"},
            ("unknown", "unknown", "execution_interrupted", ["error.type"]),
        ),
        (
            {"type": "PermissionError"},
            ("failure", "permission", "permission_error", ["error.type"]),
        ),
        (
            {"type": "OSError", "errno_name": "EBADARCH"},
            ("failure", "environment", "executable_launch_error", ["error.errno_name"]),
        ),
        (
            {"type": "OSError", "errno_name": "ENOEXEC"},
            ("failure", "environment", "executable_launch_error", ["error.errno_name"]),
        ),
        (
            {"type": "CalledProcessError", "returncode": 2},
            (
                "failure",
                "process_error",
                "process_nonzero_exit",
                ["error.type", "error.returncode"],
            ),
        ),
        (
            {"type": "FileNotFoundError", "message": "missing output"},
            ("failure", "missing_file", "missing_file_error", ["error.type"]),
        ),
        (
            {"type": "NotADirectoryError"},
            ("failure", "filesystem", "filesystem_error", ["error.type"]),
        ),
        (
            {"type": "OSError", "errno_name": "EROFS"},
            ("failure", "filesystem", "filesystem_error", ["error.errno_name"]),
        ),
        (
            {"type": "OSError", "errno_name": "ENOSPC"},
            ("failure", "resource_limit", "resource_limit_error", ["error.errno_name"]),
        ),
        (
            {"type": "MemoryError"},
            ("failure", "resource_limit", "resource_limit_error", ["error.type"]),
        ),
        (
            {"type": "TimeoutExpired"},
            ("failure", "timeout", "timeout_error", ["error.type"]),
        ),
        (
            {"type": "ReadTimeout"},
            ("failure", "timeout", "timeout_error", ["error.type"]),
        ),
        (
            {"type": "ConnectionError"},
            ("failure", "network", "network_error", ["error.type"]),
        ),
        (
            {"type": "OSError", "errno_name": "ENETUNREACH"},
            ("failure", "network", "network_error", ["error.errno_name"]),
        ),
        (
            {"type": "ValueError", "message": "missing output"},
            ("failure", "unknown", "unclassified_error", ["error"]),
        ),
    ],
)
def test_classification_preserves_records(
    tmp_path: Path,
    error: dict[str, object] | None,
    expected: tuple[str, str, str, list[str]],
) -> None:
    outcome, category, rule, evidence = expected
    source = tmp_path / "experiment.json"
    record: dict[str, object] = {"status": "finished", "stage": "evaluation"}
    if error is not None:
        record.update(
            error=error,
            acceptance={"recovery": {"min": 1}},
            evaluation={"metrics": {"recovery": 1}},
        )
    original = json.dumps(record)
    source.write_text(original)
    result = CliRunner().invoke(app, ["classify", str(tmp_path)])
    assert result.exit_code == 0, result.output
    output = tmp_path / "classification.json"
    assessment = json.loads(output.read_text())
    assert assessment == {
        "source": "experiment.json",
        "rule": rule,
        "outcome": outcome,
        "category": category,
        "detected_stage": "evaluation" if error else None,
        "evidence": evidence,
        "diagnosis": {"method": "placeholder", "origin_stage": None, "evidence": []},
    }
    output.write_text('{"outcome":"success"}')
    assert CliRunner().invoke(app, ["classify", str(tmp_path)]).exit_code == 1
    assert output.read_text() == '{"outcome":"success"}'
    assert source.read_text() == original


@pytest.mark.parametrize(
    "metrics,outcome",
    [
        ({"recovery": 1, "error_rate": 0.05}, "success"),
        ({"recovery": 0.5, "error_rate": 0}, "failure"),
        ({"recovery": 1, "error_rate": 0.1}, "failure"),
        ({"recovery": 1}, "unknown"),
        ({"recovery": 1, "error_rate": float("nan")}, "unknown"),
        ({"recovery": 0.5}, "failure"),
    ],
)
def test_classification_checks_saved_metrics(
    tmp_path: Path, metrics: dict[str, float], outcome: str
) -> None:
    criteria = {"recovery": {"min": 1}, "error_rate": {"max": 0.05}}
    (tmp_path / "experiment.json").write_text(
        json.dumps(
            {
                "status": "finished",
                "stage": "evaluation",
                "acceptance": criteria,
                "evaluation": {"metrics": metrics},
            }
        )
    )
    result = CliRunner().invoke(app, ["classify", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assessment = json.loads((tmp_path / "classification.json").read_text())
    assert assessment["outcome"] == outcome
    assert (
        assessment["category"]
        == {
            "success": None,
            "failure": "acceptance_criterion_not_met",
            "unknown": "unknown",
        }[outcome]
    )
    assert assessment["detected_stage"] == (
        "assessment" if outcome == "failure" else None
    )
    assert assessment["checks"]["recovery"]["min"] == 1
    assert assessment["checks"]["recovery"]["value"] == metrics["recovery"]
    assert assessment["checks"]["error_rate"]["max"] == 0.05
    assert assessment["evidence"] == ["acceptance", "evaluation.metrics"]
    json.dumps(assessment, allow_nan=False)


@pytest.mark.parametrize(
    "record",
    [
        None,
        "{",
        "[]",
        '{"status":"not_started"}',
        '{"status":"running","error":{"message":"missing"}}',
    ],
)
def test_classification_requires_a_finished_record(
    tmp_path: Path, record: str | None
) -> None:
    if record is not None:
        (tmp_path / "experiment.json").write_text(record)
    result = CliRunner().invoke(app, ["classify", str(tmp_path)])
    assert result.exit_code == 1
    assert "Cannot classify experiment:" in result.output
    assert not (tmp_path / "classification.json").exists()
