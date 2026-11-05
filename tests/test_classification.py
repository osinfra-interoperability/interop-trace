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
        record["error"] = error
    original = json.dumps(record)
    source.write_text(original)
    result = CliRunner().invoke(app, ["classify", str(tmp_path)])
    assert result.exit_code == 0, result.output
    output = tmp_path / "classification.json"
    assessment = json.loads(output.read_text())
    assert assessment == {
        "source": "experiment.json",
        "method": "deterministic",
        "rule": rule,
        "outcome": outcome,
        "category": category,
        "evidence": evidence,
    }
    output.write_text('{"outcome":"success"}')
    assert CliRunner().invoke(app, ["classify", str(tmp_path)]).exit_code == 1
    assert output.read_text() == '{"outcome":"success"}'
    assert source.read_text() == original


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
