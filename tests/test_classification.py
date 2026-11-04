"""Exercise post-run assessment through the CLI without classification services."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from interop_trace.interfaces.cli import app


def test_unknown_classification_preserves_records(tmp_path: Path) -> None:
    source = tmp_path / "experiment.json"
    original = '{"status":"failed","stage":"evaluation","error":{"message":"missing"}}'
    source.write_text(original)
    result = CliRunner().invoke(app, ["classify", str(tmp_path)])
    assert result.exit_code == 0, result.output
    output = tmp_path / "classification.json"
    assessment = json.loads(output.read_text())
    assert assessment == {
        "source": "experiment.json",
        "method": "placeholder",
        "outcome": "unknown",
        "category": "unknown",
        "cause": None,
        "evidence": [],
    }
    output.write_text('{"outcome":"success"}')
    assert CliRunner().invoke(app, ["classify", str(tmp_path)]).exit_code == 1
    assert output.read_text() == '{"outcome":"success"}'
    assert source.read_text() == original


@pytest.mark.parametrize("record", [None, "{", "[]", '{"status":"completed"}'])
def test_classification_rejects_missing_invalid_or_nonfailed_records(
    tmp_path: Path, record: str | None
) -> None:
    if record is not None:
        (tmp_path / "experiment.json").write_text(record)
    result = CliRunner().invoke(app, ["classify", str(tmp_path)])
    assert result.exit_code == 1
    assert "Cannot classify experiment:" in result.output
    assert not (tmp_path / "classification.json").exists()
