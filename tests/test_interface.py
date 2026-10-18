"""Exercise real NiceGUI events without a browser or scientific downloads."""

import json
import shutil
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
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
    from interop_trace.interfaces.web.app import _Dashboard
    from interop_trace.interfaces.web.runs import RunBrowser

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

    monkeypatch.setattr("interop_trace.interfaces.web.runs.subprocess.Popen", launch)
    previous = checkout / "results/previous"
    previous.mkdir(parents=True)
    (previous / "configuration.json").write_text('{"experiments": []}')
    _page(checkout)
    await user.open("/")
    await user.should_see("Selected: 0 of 1 experiments", retries=10)
    assert any(
        row.get("database") == "erwinia_and_spikes"
        for table in user.find(nicegui.ui.table).elements
        for row in table.rows
    )
    await user.should_see("Status: unknown")
    assert not user.find(marker="start-run").elements.pop().enabled
    table = user.find(marker="experiment-choices")
    rows = table.elements.copy().pop().rows
    table.trigger("selection", {"added": True, "rows": rows, "keys": ["erwinia_sage"]})
    user.find(marker="start-run").click()
    await user.should_see("Status: running")
    assert output is not None
    user.find("Files and provenance").click()
    user.find(marker="output-file").click()
    user.find("Console log").click()
    await user.should_see("native tool log")
    with output.with_name(output.name + ".console.log").open("a") as stream:
        stream.write("progress update\n")
    await user.should_see("progress update", retries=20)
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
    report = output / "erwinia_sage/evaluation/expected_peptides.json"
    report.parent.mkdir()
    report.write_text(json.dumps({"metrics": {"matched_expected_peptides": 4}}))
    process.poll.return_value = 0
    await user.should_see("Status: completed", retries=20)
    assert any(
        row.get("id") == "erwinia_sage" and row.get("status") == "completed"
        for table in user.find(nicegui.ui.table).elements
        for row in table.rows
    )
    assert user.find(marker="start-run").elements.pop().enabled
    user.find(marker="output-file").click()
    user.find("configuration.json").click()
    await user.should_see('"experiments"')
    download = Mock()
    monkeypatch.setattr(user.download, "file", download)
    user.find(marker="download-file").click()
    download.assert_called_once_with(output / "configuration.json")
    user.find(marker="file-group").click()
    user.find("Experiment: erwinia_sage").click()
    await user.should_see('"matched_expected_peptides": 4')
    user.find(marker="download-file").click()
    download.assert_called_with(report)
    http_transport.assert_not_called()


async def test_empty_checkout_keeps_run_disabled(
    user, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _page(tmp_path)
    await user.open("/")
    await user.should_see("No experiments found")
    assert not user.find(marker="start-run").elements.pop().enabled


async def test_selecting_an_output_displays_its_content(user, checkout: Path) -> None:
    directory = checkout / "results/example"
    directory.mkdir(parents=True)
    snapshot = '{"experiments": [], "reference": "original configuration"}'
    (directory / "configuration.json").write_text(snapshot)
    (directory / "results.tsv").write_text("protein\tscore\nP00924\t42")
    (directory / "output.bin").write_bytes(b"\x00\x01binary")
    _page(checkout)
    await user.open("/")
    user.find("Files and provenance").click()
    await user.should_see("original configuration", retries=10)
    viewer = user.find(nicegui.ui.codemirror).elements.pop()
    assert viewer.language == "JSON" and not viewer.enabled
    user.find(marker="output-file").click()
    user.find("results.tsv").click()
    await user.should_see("P00924\t42")
    assert viewer.language is None
    await user.should_not_see("original configuration")
    user.find(marker="output-file").click()
    user.find("output.bin").click()
    await user.should_see("Binary file: use Download file to inspect it.")
    await user.should_not_see("P00924\t42")
    user.find(marker="output-file").click()
    user.find("configuration.json").click()
    await user.should_see("original configuration")
    assert viewer.language == "JSON"


async def test_files_and_logs_are_scoped_to_root_or_one_experiment(
    user, checkout: Path
) -> None:
    directory = checkout / "results/grouped"
    directory.mkdir(parents=True)
    (directory / "configuration.json").write_text(
        json.dumps(
            {
                "experiments": [
                    {"id": name} for name in ("first", "second", "pending")
                ],
                "note": "run-level configuration",
            }
        )
    )
    directory.with_name("grouped.console.log").write_text("run-level console")
    for name in ("first", "second"):
        folder = directory / name / "workflow"
        folder.mkdir(parents=True)
        (folder / "settings.json").write_text(json.dumps({"note": f"{name} settings"}))
        (folder / "sage.log").write_text(f"{name} log")
    _page(checkout)
    await user.open("/")
    user.find("Files and provenance").click()
    await user.should_see("run-level configuration", retries=10)
    user.find(marker="output-file").click()
    user.find("Console log").click()
    await user.should_see("run-level console")
    selector = user.find(marker="output-file").elements.pop()
    assert set(selector.options.values()) == {"configuration.json", "Console log"}

    for name in ("first", "second"):
        user.find(marker="file-group").click()
        user.find(f"Experiment: {name}").click()
        await user.should_see(f"{name} log", retries=10)
        assert set(selector.options.values()) == {
            "workflow/settings.json",
            "workflow/sage.log",
        }
        assert all(Path(p).is_relative_to(directory / name) for p in selector.options)
        user.find(marker="output-file").click()
        user.find("workflow/settings.json").click()
        await user.should_see(f"{name} settings")
        await user.should_not_see("run-level configuration")

    user.find(marker="file-group").click()
    user.find("Experiment: pending").click()
    await user.should_see("No output file selected.")
    assert not selector.options
    user.find(marker="file-group").click()
    user.find("Run-level files").click()
    await user.should_see("run-level configuration")
    user.find(marker="output-file").click()
    user.find("Console log").click()
    await user.should_see("run-level console")


async def test_failed_process_shows_console_error_and_allows_another_run(
    user, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock()
    process.poll.return_value = 1

    def fail(command, **kwargs):
        kwargs["stdout"].write(b"Run failed: missing input\n")
        kwargs["stdout"].flush()
        return process

    monkeypatch.setattr("interop_trace.interfaces.web.runs.subprocess.Popen", fail)
    _page(checkout)
    await user.open("/")
    await user.should_see("Selected: 0 of 1 experiments", retries=10)
    table = user.find(marker="experiment-choices")
    rows = table.elements.copy().pop().rows
    table.trigger("selection", {"added": True, "rows": rows, "keys": ["erwinia_sage"]})
    user.find(marker="start-run").click()
    await user.should_see("Status: failed")
    user.find("Files and provenance").click()
    await user.should_see("Run failed: missing input")
    assert user.find(marker="start-run").elements.pop().enabled


async def test_checkboxes_select_ids_across_files(
    user, checkout: Path, monkeypatch: pytest.MonkeyPatch, http_transport: Mock
) -> None:
    source = checkout / "experiments/simple.yaml"
    document = yaml.safe_load(source.read_text())
    document["experiments"] = [
        {**document["experiments"][0], "id": name} for name in ("another", "third")
    ]
    (source.parent / "other.yml").write_text(yaml.safe_dump(document))
    process = Mock()
    process.poll.return_value = 1
    launch = Mock(return_value=process)
    monkeypatch.setattr("interop_trace.interfaces.web.runs.subprocess.Popen", launch)
    _page(checkout)
    await user.open("/")
    await user.should_see("Selected: 0 of 3 experiments", retries=10)
    table = user.find(marker="experiment-choices")
    rows = [r for r in table.elements.copy().pop().rows if r["id"] != "third"]
    table.trigger(
        "selection", {"added": True, "rows": rows, "keys": [r["id"] for r in rows]}
    )
    await user.should_see("Selected: 2 of 3 experiments")
    user.find(marker="start-run").click()
    await user.should_see("Status: failed", retries=10)
    command = launch.call_args.args[0]
    assert command[4 : command.index("--directory")] == ["another", "erwinia_sage"]
    http_transport.assert_not_called()


def test_cli_passes_directory_and_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve = Mock()
    monkeypatch.setattr("interop_trace.interfaces.web.app.serve", serve)
    result = CliRunner().invoke(
        app, ["ui", "--directory", str(tmp_path), "--port", "8093"]
    )
    assert result.exit_code == 0, result.output
    serve.assert_called_once_with(tmp_path, 8093)
