"""Check Comet installation, native invocation and failure evidence offline."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.downloads import DownloadCache
from interop_trace.workflows import CometWorkflow


@pytest.mark.parametrize(
    "system, machine, asset",
    [
        ("Darwin", "arm64", "aarch64.macos"),
        ("Darwin", "x86_64", "macos"),
        ("Linux", "aarch64", "aarch64.linux"),
        ("Linux", "x86_64", "linux"),
        ("Windows", "AMD64", "win64"),
    ],
)
def test_setup_caches_the_platform_binary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
    system: str,
    machine: str,
    asset: str,
) -> None:
    monkeypatch.setattr("interop_trace.workflows.comet.platform.system", lambda: system)
    monkeypatch.setattr(
        "interop_trace.workflows.comet.platform.machine", lambda: machine
    )
    workflow = CometWorkflow(tmp_path / "settings.params")
    cache = DownloadCache(tmp_path / "cache")
    workflow.setup(cache=cache)
    workflow.setup(cache=cache)
    http_transport.assert_called_once()
    assert cache.entries()[0].url.endswith(f"v2026.03.0/comet.{asset}.exe")
    assert cache.entries()[0].name == "comet"


@pytest.mark.parametrize("fails", [False, True])
def test_run_overrides_inputs_and_preserves_settings_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, http_transport: Mock, fails: bool
) -> None:
    settings = tmp_path / "native settings.params"
    settings.write_text("num_threads = 2\n")
    executable = tmp_path / "comet"
    executable.touch()
    workflow = CometWorkflow(settings, executable=executable)
    dataset = Dataset((tmp_path / "first.mgf", tmp_path / "second.mgf"))
    database = Database(tmp_path / "proteins.fasta", "fasta")
    output = tmp_path / "results"

    def search(command, **kwargs):
        kwargs["stdout"].write("Comet version test\n")
        assert command[1] == f"-P{output / 'comet.params'}"
        assert command[2] == f"-D{database.path}"
        assert Path(command[-1]) in dataset.files
        if fails:
            raise subprocess.CalledProcessError(1, command)
        Path(command[3][2:] + ".txt").write_text("native output")

    monkeypatch.setattr("subprocess.run", search)
    workflow.setup(cache=DownloadCache(tmp_path / "cache"))
    if fails:
        with pytest.raises(subprocess.CalledProcessError):
            workflow.run(dataset, database, output_dir=output)
    else:
        result = workflow.run(dataset, database, output_dir=output)
        assert result.format == "comet"
        assert {"001.comet.txt", "002.comet.txt"} <= result.files.keys()
        with pytest.raises(FileExistsError):
            workflow.run(dataset, database, output_dir=output)
    assert (output / "comet.params").read_bytes() == settings.read_bytes()
    assert "Comet version test" in (output / "001.comet.log").read_text()
    record = json.loads((output / "001.comet.command.json").read_text())
    assert record["command"][0] == str(executable)
    http_transport.assert_not_called()
