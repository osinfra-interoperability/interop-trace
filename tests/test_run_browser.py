"""Check launch isolation, failure visibility and history without a web server."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.run_browser import RunBrowser, console_log, log_tail, read_record


def test_launch_validates_and_allows_only_one_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "experiments/runs/example.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("an invalid configuration")
    browser = RunBrowser(tmp_path)
    popen = Mock()
    monkeypatch.setattr("interop_trace.run_browser.subprocess.Popen", popen)
    with pytest.raises(ValueError):
        browser.start(source)
    popen.assert_not_called()
    assert not (tmp_path / "results").exists()

    monkeypatch.setattr("interop_trace.run_browser.load_configuration", Mock())
    process = popen.return_value
    process.poll.return_value = None
    output = browser.start(source)
    arguments, options = popen.call_args
    assert arguments[0][1:4] == ["-m", "interop_trace", "run"]
    assert str(source) in arguments[0] and str(output) in arguments[0]
    assert options["cwd"] == tmp_path
    assert options["env"]["PYTHONUNBUFFERED"] == "1"
    assert console_log(output).is_file()
    assert not output.exists()  # The existing runner creates its own directory.
    with pytest.raises(RuntimeError, match="already active"):
        browser.start(source)
    assert popen.call_count == 1
    assert browser.history()[0].status == "running"
    process.poll.return_value = 1
    assert browser.history()[0].status == "failed"
    assert not browser.active


def test_configuration_must_belong_to_the_checkout(tmp_path: Path) -> None:
    outside = tmp_path / "other.yaml"
    outside.write_text("anything")
    with pytest.raises(ValueError, match="experiments/runs"):
        RunBrowser(tmp_path).start(outside)


@pytest.mark.parametrize(
    "statuses, expected",
    [
        (["completed", "completed"], "completed"),
        (["failed", None], "failed"),
        (["running", None], "unknown"),
    ],
)
def test_history_uses_records_and_does_not_claim_old_jobs_are_live(
    tmp_path: Path, statuses: list[str | None], expected: str
) -> None:
    directory = tmp_path / "results/cli-run"
    directory.mkdir(parents=True)
    (directory / "configuration.json").write_text(
        json.dumps({"experiments": [{"id": "first"}, {"id": "second"}]})
    )
    for name, status in zip(("first", "second"), statuses, strict=True):
        if status is not None:
            folder = directory / name
            folder.mkdir()
            (folder / "experiment.json").write_text(
                json.dumps({"id": name, "status": status, "stage": "evaluation"})
            )
    run = RunBrowser(tmp_path).history()[0]
    assert run.status == expected
    assert [record["id"] for record in run.experiments] == ["first", "second"]
    if statuses[1] is None:
        assert run.experiments[1]["status"] == "not_started"


def test_partial_record_and_large_log_are_safe_to_poll(tmp_path: Path) -> None:
    record = tmp_path / "record.json"
    record.write_text('{"status":')
    assert read_record(record) == {}
    record.write_text('{"status":"completed"}')
    assert read_record(record)["status"] == "completed"
    log = tmp_path / "console.log"
    log.write_bytes(b"x" * 100_000 + b"\nfinished")
    assert log_tail(log, 32).endswith("finished")
    assert len(log_tail(log, 32)) == 32
