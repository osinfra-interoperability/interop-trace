"""Check launch isolation, failure visibility and history without a web server."""

import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.interfaces.web.runs import (
    RunBrowser,
    console_log,
    file_preview,
    log_tail,
    read_record,
)
from interop_trace.status import ExecutionStatus


def test_launch_validates_and_allows_only_one_process(
    configuration: Path, monkeypatch: pytest.MonkeyPatch, http_transport: Mock
) -> None:
    checkout = configuration.parent.parent
    browser = RunBrowser(checkout)
    popen = Mock()
    monkeypatch.setattr("interop_trace.interfaces.web.runs.subprocess.Popen", popen)
    output = browser.create("example", ["first"])
    assert browser.history()[0].status == "not_started"
    assert (output / "experiments.csv").is_file()
    http_transport.assert_not_called()
    popen.assert_not_called()
    process = popen.return_value
    process.poll.return_value = None
    browser.start(output)
    arguments, options = popen.call_args
    assert arguments[0][1:] == ["-m", "interop_trace", "execute", str(output)]
    assert options["cwd"] == checkout
    assert options["env"]["PYTHONUNBUFFERED"] == "1"
    assert console_log(output).is_file()
    with pytest.raises(RuntimeError, match="already active"):
        browser.start(output)
    assert popen.call_count == 1
    assert browser.history()[0].status == "running"
    process.poll.return_value = 1
    assert browser.history()[0].status == "finished"
    assert not browser.active


@pytest.mark.parametrize(
    "name, ids, message",
    [
        ("example", ["missing"], "Unknown experiment IDs"),
        ("../escape", ["first"], "Run names"),
    ],
)
def test_invalid_creation_leaves_no_outputs(
    configuration: Path, name: str, ids: list[str], message: str
) -> None:
    checkout = configuration.parent.parent
    with pytest.raises(ValueError, match=message):
        RunBrowser(checkout).create(name, ids)
    assert not (checkout / "results").exists()


def test_active_batch_stays_running_after_an_experiment_fails(
    configuration: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock()
    process.poll.return_value = None
    monkeypatch.setattr(
        "interop_trace.interfaces.web.runs.subprocess.Popen", Mock(return_value=process)
    )
    browser = RunBrowser(configuration.parent.parent)
    output = browser.create("example", ["first"])
    browser.start(output)
    (output / "first/experiment.json").write_text(
        '{"status":"finished","error":{"type":"ValueError","message":"missing"}}'
    )
    saved = browser.history()[0]
    assert saved.status == "running"
    assert saved.experiments[0]["status"] == "finished"
    assert saved.experiments[0]["error"] == "ValueError"
    process.poll.return_value = 1
    assert browser.history()[0].status == "finished"


def test_early_failures_remain_visible_after_later_launches(
    configuration: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock()
    process.poll.return_value = 1
    monkeypatch.setattr(
        "interop_trace.interfaces.web.runs.subprocess.Popen", Mock(return_value=process)
    )
    browser = RunBrowser(configuration.parent.parent)
    browser.start(browser.create("first-run", ["first"]))
    browser.start(browser.create("second-run", ["first"]))
    assert [run.status for run in browser.history()] == ["finished", "finished"]


@pytest.mark.parametrize(
    "statuses, expected",
    [
        (["finished", "finished"], "finished"),
        (["finished", None], None),
        (["running", None], None),
    ],
)
def test_history_uses_records_and_does_not_claim_old_jobs_are_live(
    tmp_path: Path, statuses: list[str | None], expected: str | None
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
    assert run.status is (ExecutionStatus(expected) if expected else None)
    assert [record["id"] for record in run.experiments] == ["first", "second"]
    if statuses[1] is None:
        assert run.experiments[1]["status"] == "not_started"


def test_partial_record_and_large_log_are_safe_to_poll(tmp_path: Path) -> None:
    record = tmp_path / "record.json"
    record.write_text('{"status":')
    assert read_record(record) == {}
    record.write_text('{"status":"finished"}')
    assert read_record(record)["status"] == "finished"
    log = tmp_path / "console.log"
    log.write_bytes(b"x" * 100_000 + b"\nfinished")
    assert log_tail(log, 32).endswith("finished")
    assert len(log_tail(log, 32)) == 32
    assert file_preview(log, 32) == log_tail(log, 32)


def test_history_keeps_the_snapshot_id_for_file_grouping(tmp_path: Path) -> None:
    directory = tmp_path / "results/example"
    (directory / "first").mkdir(parents=True)
    (directory / "configuration.json").write_text('{"experiments": [{"id": "first"}]}')
    (directory / "first/experiment.json").write_text(
        '{"id": "../other", "status": "finished"}'
    )
    saved = RunBrowser(tmp_path).history()[0]
    assert saved.experiments[0]["id"] == "first"
    assert saved.status == "finished"


def test_history_orders_by_time_rather_than_name(tmp_path: Path) -> None:
    for name, timestamp in (("z-old", 1), ("a-new", 2)):
        path = tmp_path / "results" / name
        path.mkdir(parents=True)
        (path / "configuration.json").write_text("{}")
        os.utime(path, (timestamp, timestamp))
    assert [r.directory.name for r in RunBrowser(tmp_path).history()] == [
        "a-new",
        "z-old",
    ]


def test_file_preview_bounds_large_text_and_handles_split_utf8(tmp_path: Path) -> None:
    path = tmp_path / "results.tsv"
    path.write_text("protein\tscore\n" + "a" * 100_000, encoding="utf-8")
    preview = file_preview(path, 32)
    assert preview.startswith("protein\tscore\n" + "a" * 18)
    assert "Preview truncated" in preview
    assert len(preview) < 100
    path.write_text("café", encoding="utf-8")
    assert file_preview(path, 4).startswith("caf\n\n[Preview truncated")


@pytest.mark.parametrize("content", [b"\x00\x01binary", b"\xff\xfebinary"])
def test_file_preview_explains_binary_files(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "output.bin"
    path.write_bytes(content)
    assert "use Download file" in file_preview(path)


def test_file_preview_handles_empty_and_missing_files(tmp_path: Path) -> None:
    path = tmp_path / "output.txt"
    assert file_preview(path) == "File not available."
    path.touch()
    assert file_preview(path) == "Empty file."
