"""Check launch isolation, failure visibility and history without a web server."""

import json
import os
import shutil
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


def test_launch_validates_and_allows_only_one_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "experiments/example.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("an invalid configuration")
    browser = RunBrowser(tmp_path)
    popen = Mock()
    monkeypatch.setattr("interop_trace.interfaces.web.runs.subprocess.Popen", popen)
    with pytest.raises(ValueError):
        browser.start(["first"])
    popen.assert_not_called()
    assert not (tmp_path / "results").exists()

    monkeypatch.setattr("interop_trace.interfaces.web.runs.load_experiments", Mock())
    process = popen.return_value
    process.poll.return_value = None
    output = browser.start(["first"])
    arguments, options = popen.call_args
    assert arguments[0][1:4] == ["-m", "interop_trace", "run"]
    assert arguments[0][4] == "first"
    assert str(source.parent) in arguments[0] and str(output) in arguments[0]
    assert options["cwd"] == tmp_path
    assert options["env"]["PYTHONUNBUFFERED"] == "1"
    assert console_log(output).is_file()
    assert not output.exists()  # The existing runner creates its own directory.
    with pytest.raises(RuntimeError, match="already active"):
        browser.start(["first"])
    assert popen.call_count == 1
    assert browser.history()[0].status == "running"
    process.poll.return_value = 1
    assert browser.history()[0].status == "failed"
    assert not browser.active


def test_unknown_ids_fail_before_creating_outputs(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "experiments"
    shutil.copytree(source, tmp_path / "experiments")
    with pytest.raises(ValueError, match="Unknown experiment IDs"):
        RunBrowser(tmp_path).start(["missing"])
    assert not (tmp_path / "results").exists()


def test_early_failures_remain_visible_after_later_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "experiments/example.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("validated below")
    monkeypatch.setattr("interop_trace.interfaces.web.runs.load_experiments", Mock())
    process = Mock()
    process.poll.return_value = 1
    monkeypatch.setattr(
        "interop_trace.interfaces.web.runs.subprocess.Popen", Mock(return_value=process)
    )
    browser = RunBrowser(tmp_path)
    browser.start(["first"])
    browser.start(["first"])
    assert [run.status for run in browser.history()] == ["failed", "failed"]


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


def test_history_keeps_the_snapshot_id_for_file_grouping(tmp_path: Path) -> None:
    directory = tmp_path / "results/example"
    (directory / "first").mkdir(parents=True)
    (directory / "configuration.json").write_text('{"experiments": [{"id": "first"}]}')
    (directory / "first/experiment.json").write_text(
        '{"id": "../other", "status": "completed"}'
    )
    saved = RunBrowser(tmp_path).history()[0]
    assert saved.experiments[0]["id"] == "first"
    assert saved.status == "completed"


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
