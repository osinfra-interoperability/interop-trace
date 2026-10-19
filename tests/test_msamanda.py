"""Exercise Amanda's bundle and XML/process boundary without native software."""

import json
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.downloads import DownloadCache
from interop_trace.workflows import MSAmandaWorkflow


@pytest.mark.parametrize(
    "system, target", [("Darwin", "Mac"), ("Linux", "Linux"), ("Windows", "Win")]
)
def test_setup_reuses_the_complete_standalone_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
    http_response,
    system: str,
    target: str,
) -> None:
    monkeypatch.setattr(
        "interop_trace.workflows.msamanda.platform.system", lambda: system
    )
    monkeypatch.setattr(
        "interop_trace.workflows.msamanda.platform.machine", lambda: "x86_64"
    )
    binary = "MSAmanda.exe" if system == "Windows" else "MSAmanda"
    name = f"MSAmanda_{target}_3.0.22.864"
    files = {
        binary: b"binary",
        "enzymes.xml": b"<Enzymes/>",
        "modifications.xml": b"<Modifications/>",
    }
    buffer = BytesIO()
    if system == "Windows":
        with zipfile.ZipFile(buffer, "w") as archive:
            for filename, content in files.items():
                archive.writestr(f"{name}/{filename}", content)
    else:
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for filename, content in files.items():
                member = tarfile.TarInfo(f"{name}/{filename}")
                member.size = len(content)
                archive.addfile(member, BytesIO(content))
    http_transport.side_effect = lambda request: http_response(buffer.getvalue())
    cache = DownloadCache(tmp_path / "cache")
    workflow = MSAmandaWorkflow(tmp_path / "settings.xml")
    workflow.setup(cache=cache)
    workflow.setup(cache=cache)
    http_transport.assert_called_once()
    entry = cache.entries()[0]
    assert entry.name == "msamanda" and entry.kind == "workflow"
    assert f"/3.0.22.864/{target.lower()}/{name}" in entry.url


@pytest.mark.parametrize("fails", [False, True])
def test_run_preserves_resolved_settings_definitions_and_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, http_transport: Mock, fails: bool
) -> None:
    settings = tmp_path / "settings.xml"
    settings.write_text(
        "<Settings><SearchSettings><MaxRank>1</MaxRank></SearchSettings></Settings>"
    )
    executable = tmp_path / "MSAmanda"
    executable.touch()
    for name in ("enzymes.xml", "modifications.xml"):
        (tmp_path / name).write_text("<Definitions/>")
    workflow = MSAmandaWorkflow(settings, executable=executable, threads=3)
    workflow.setup(cache=DownloadCache(tmp_path / "cache"))
    output = tmp_path / "results with spaces"
    source = tmp_path / "spectra.mgf"
    database = Database(tmp_path / "proteins.fasta", "fasta")

    def search(command, **kwargs):
        assert command[command.index("-s") + 1] == str(source)
        assert command[command.index("-d") + 1] == str(database.path)
        resolved = Path(command[command.index("-e") + 1])
        assert ET.parse(resolved).findtext("SearchSettings/MaxRank") == "1"
        basic = ET.parse(resolved).find("BasicSettings")
        assert basic is not None
        assert basic.findtext("DataFolder") == str(output / "runtime")
        assert Path(basic.findtext("EnzymesFile")).read_text() == "<Definitions/>"
        assert kwargs["env"]["DOTNET_PROCESSOR_COUNT"] == "3"
        kwargs["stdout"].write("MS Amanda version test\n")
        if fails:
            raise subprocess.CalledProcessError(1, command)
        Path(command[command.index("-o") + 1]).write_text("native results")

    monkeypatch.setattr("subprocess.run", search)
    if fails:
        with pytest.raises(subprocess.CalledProcessError):
            workflow.run(Dataset((source,)), database, output_dir=output)
    else:
        result = workflow.run(Dataset((source,)), database, output_dir=output)
        assert "001.msamanda.csv" in result.files and result.format == "msamanda"
        with pytest.raises(FileExistsError):
            workflow.run(Dataset((source,)), database, output_dir=output)
    assert (output / "msamanda-input.xml").read_bytes() == settings.read_bytes()
    assert "version test" in (output / "001.msamanda.log").read_text()
    record = json.loads((output / "001.msamanda.command.json").read_text())
    assert record["command"][0] == str(executable)
    http_transport.assert_not_called()


def test_arm_linux_requires_a_supplied_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, http_transport: Mock
) -> None:
    monkeypatch.setattr(
        "interop_trace.workflows.msamanda.platform.system", lambda: "Linux"
    )
    monkeypatch.setattr(
        "interop_trace.workflows.msamanda.platform.machine", lambda: "aarch64"
    )
    with pytest.raises(ValueError, match="No MS Amanda download"):
        MSAmandaWorkflow(tmp_path / "settings.xml").setup(
            cache=DownloadCache(tmp_path / "cache")
        )
    http_transport.assert_not_called()
