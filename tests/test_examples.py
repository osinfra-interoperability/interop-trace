"""Keep the documented experiments constructible without network access."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from interop_trace.experiments import load_configuration
from interop_trace.interfaces.cli import app
from interop_trace.workflows import SageWorkflow


def test_simple_configuration_from_another_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
) -> None:
    path = Path(__file__).resolve().parents[1] / "experiments/simple.yaml"
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["run", "erwinia_sage", "--directory", str(path.parent), "--check"]
    )
    assert result.exit_code == 0, result.output
    assert "1 experiment(s)" in result.output
    # YAML construction does not check native file existence; catch broken moves.
    workflow = load_configuration(path).experiments[0].workflow
    assert isinstance(workflow, SageWorkflow)
    assert workflow.configuration.is_file()
    http_transport.assert_not_called()
    assert not (tmp_path / ".interop_trace").exists()
