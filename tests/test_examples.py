"""Keep the documented experiments constructible without network access."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from interop_trace.cli import app


def test_simple_configuration_from_another_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
) -> None:
    path = Path(__file__).resolve().parents[1] / "experiments/simple" / "run.yaml"
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["run", str(path), "--check"])
    assert result.exit_code == 0, result.output
    assert "1 experiment(s)" in result.output
    http_transport.assert_not_called()
    assert not (tmp_path / ".interop_trace").exists()
