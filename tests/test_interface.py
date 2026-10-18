"""Exercise real NiceGUI events without a browser or scientific downloads."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from interop_trace.interfaces.cli import app

nicegui = pytest.importorskip("nicegui")


@pytest.fixture
async def user(caplog):
    from nicegui.testing.user_simulation import user_simulation

    async with user_simulation() as simulated:
        yield simulated
    assert not [r for r in caplog.get_records("call") if r.levelname == "ERROR"]


def _page(directory: Path) -> None:
    from interop_trace.interface import _Dashboard
    from interop_trace.run_browser import RunBrowser

    browser = RunBrowser(directory)

    @nicegui.ui.page("/")
    async def index() -> None:
        dashboard = _Dashboard(browser)
        await dashboard.preview()
        await dashboard.refresh()


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "experiments"
    shutil.copytree(source, tmp_path / "experiments")
    return tmp_path


async def test_launch_monitor_and_download(
    user, checkout: Path, monkeypatch: pytest.MonkeyPatch, http_transport: Mock
) -> None:
    process = Mock()
    process.poll.return_value = None
    output: Path | None = None

    def launch(command, **kwargs):
        nonlocal output
        output = Path(command[command.index("--output") + 1])
        (output / "erwinia_sage").mkdir(parents=True)
        (output / "configuration.json").write_text(
            json.dumps({"experiments": [{"id": "erwinia_sage"}]})
        )
        (output / "erwinia_sage/experiment.json").write_text(
            json.dumps({"id": "erwinia_sage", "status": "running", "stage": "workflow"})
        )
        kwargs["stdout"].write(b"native tool log\n")
        kwargs["stdout"].flush()
        return process

    monkeypatch.setattr("interop_trace.run_browser.subprocess.Popen", launch)
    _page(checkout)
    await user.open("/")
    await user.should_see("Experiments: 1", retries=10)
    assert any(
        row.get("database") == "erwinia_and_spikes"
        for table in user.find(nicegui.ui.table).elements
        for row in table.rows
    )
    user.find(marker="start-run").click()
    await user.should_see("Status: running")
    await user.should_see("native tool log")
    assert output is not None
    assert not user.find(marker="start-run").elements.pop().enabled
    (output / "erwinia_sage/experiment.json").write_text(
        json.dumps(
            {
                "id": "erwinia_sage",
                "status": "completed",
                "stage": "evaluation",
                "evaluation": {"metrics": {"matched_expected_peptides": 4}},
            }
        )
    )
    process.poll.return_value = 0
    await user.should_see("Status: completed", retries=10)
    assert any(
        row.get("metric") == "matched_expected_peptides" and row["value"] == 4
        for table in user.find(nicegui.ui.table).elements
        for row in table.rows
    )
    assert user.find(marker="start-run").elements.pop().enabled
    user.find("Files and provenance").click()
    download = Mock()
    monkeypatch.setattr(user.download, "file", download)
    user.find(marker="download-file").click()
    download.assert_called_once_with(output / "configuration.json")
    http_transport.assert_not_called()


async def test_empty_checkout_keeps_run_disabled(
    user, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _page(tmp_path)
    await user.open("/")
    await user.should_see("No configurations found")
    assert not user.find(marker="start-run").elements.pop().enabled


async def test_failed_process_shows_console_error_and_allows_another_run(
    user, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock()
    process.poll.return_value = 1

    def fail(command, **kwargs):
        kwargs["stdout"].write(b"Run failed: missing input\n")
        kwargs["stdout"].flush()
        return process

    monkeypatch.setattr("interop_trace.run_browser.subprocess.Popen", fail)
    _page(checkout)
    await user.open("/")
    await user.should_see("Experiments: 1", retries=10)
    user.find(marker="start-run").click()
    await user.should_see("Status: failed")
    await user.should_see("Run failed: missing input")
    assert user.find(marker="start-run").elements.pop().enabled


def test_cli_passes_directory_and_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve = Mock()
    monkeypatch.setattr("interop_trace.interface.serve", serve)
    result = CliRunner().invoke(
        app, ["ui", "--directory", str(tmp_path), "--port", "8093"]
    )
    assert result.exit_code == 0, result.output
    serve.assert_called_once_with(tmp_path, 8093)
