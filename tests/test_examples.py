"""Keep the documented experiments constructible without network access."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from interop_trace.experiments import load_experiments
from interop_trace.interfaces.cli import app
from interop_trace.workflows import CometWorkflow, MSAmandaWorkflow, SageWorkflow


@pytest.mark.parametrize(
    "experiment_id, workflow_type",
    [
        ("erwinia_sage", SageWorkflow),
        ("erwinia_comet", CometWorkflow),
        ("erwinia_msamanda", MSAmandaWorkflow),
    ],
)
def test_documented_experiment_from_another_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
    experiment_id: str,
    workflow_type: type,
) -> None:
    directory = Path(__file__).resolve().parents[1] / "experiments"
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["run", experiment_id, "--directory", str(directory), "--check"]
    )
    assert result.exit_code == 0, result.output
    assert "1 experiment(s)" in result.output
    # YAML construction does not check native file existence; catch broken moves.
    workflow = load_experiments(directory, [experiment_id]).experiments[0].workflow
    assert isinstance(workflow, workflow_type)
    assert workflow.configuration.is_file()
    http_transport.assert_not_called()
    assert not (tmp_path / ".interop_trace").exists()
