"""Run MS Amanda standalone with native XML settings."""

import platform
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import pooch

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.downloads import DownloadCache
from interop_trace.workflows._execution import (
    measurement_files,
    run_command,
    workflow_result,
)
from interop_trace.workflows.base import WorkflowResult
from interop_trace.workflows.registry import registry

# Pin the distribution repository as well as the release directory.
_REVISION = "61790e9fe363ae7052a6aef13423dc9a2dbe37c7"


@registry.register(
    "msamanda",
    summary="Local MS Amanda peptide identification",
    documentation="components.md#msamanda",
    paths=("configuration", "executable"),
)
@dataclass
class MSAmandaWorkflow:
    """Standalone distribution; the Intel macOS build needs Rosetta on ARM Macs."""

    configuration: Path
    executable: Path | None = None
    version: str = "3.0.22.864"
    threads: int = 2
    _executable: Path | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.threads) is not int or self.threads < 1:
            raise ValueError("MS Amanda threads must be a positive integer.")

    def setup(self, *, cache: DownloadCache) -> None:
        """Cache the standalone bundle, including its runtime and definitions."""
        self._executable = None
        if self.executable is not None:
            executable = self.executable.resolve()
        else:
            system, machine = platform.system(), platform.machine().lower()
            if (system != "Darwin" and machine not in {"x86_64", "amd64"}) or (
                system == "Darwin" and machine not in {"x86_64", "arm64"}
            ):
                raise ValueError(f"No MS Amanda download for {system}/{machine}.")
            try:
                target = {"Darwin": "Mac", "Linux": "Linux", "Windows": "Win"}[system]
            except KeyError:
                raise ValueError(
                    f"No MS Amanda download for {system}/{machine}."
                ) from None
            suffix = ".zip" if system == "Windows" else ".tar.gz"
            name = f"MSAmanda_{target}_{self.version}"
            url = (
                "https://raw.githubusercontent.com/hgb-bin-proteomics/MSAmanda/"
                f"{_REVISION}/release/sa/{self.version}/{target.lower()}/{name}{suffix}"
            )
            archive = cache.fetch(
                url,
                name="msamanda",
                kind="workflow",
                metadata={"version": self.version, "revision": _REVISION},
            )
            extractor = pooch.Unzip if system == "Windows" else pooch.Untar
            extractor(extract_dir="extracted")(str(archive.path), "fetch", None)
            binary = "MSAmanda.exe" if system == "Windows" else "MSAmanda"
            executable = archive.path.parent / "extracted" / name / binary
        if not executable.is_file():
            raise FileNotFoundError(executable)
        self._executable = executable

    def run(
        self, dataset: Dataset, database: Database, *, output_dir: Path
    ) -> WorkflowResult:
        """Save resolved settings and definitions, then search each measurement."""
        if self._executable is None:
            raise RuntimeError("Call MSAmandaWorkflow.setup(cache=...) before run().")
        files = measurement_files(dataset)
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        settings = self._settings(output_dir)
        for index, source in enumerate(files, 1):
            base = output_dir / f"{index:03}.msamanda"
            run_command(
                [
                    str(self._executable),
                    "-s",
                    str(source),
                    "-d",
                    str(database.path.resolve()),
                    "-e",
                    str(settings),
                    "-f",
                    "1",
                    "-o",
                    str(base.with_suffix(".msamanda.csv")),
                ],
                base.with_suffix(".msamanda.log"),
                output_dir,
                {"DOTNET_PROCESSOR_COUNT": str(self.threads)},
            )
        return workflow_result("msamanda", output_dir)

    def _settings(self, directory: Path) -> Path:
        assert self._executable is not None
        original = directory / "msamanda-input.xml"
        shutil.copyfile(self.configuration, original)
        tree = ET.parse(original)
        basic = tree.getroot().find("BasicSettings")
        if basic is None:
            basic = ET.SubElement(tree.getroot(), "BasicSettings")
        for tag, filename in (
            ("EnzymesFile", "enzymes.xml"),
            ("ModificationsFile", "modifications.xml"),
        ):
            node = basic.find(tag)
            if node is None:
                node = ET.SubElement(basic, tag)
            source = (
                self.configuration.resolve().parent / node.text
                if node.text
                else self._executable.parent / filename
            )
            shutil.copyfile(source, directory / filename)
            node.text = str(directory / filename)
        data = basic.find("DataFolder")
        if data is None:
            data = ET.SubElement(basic, "DataFolder")
        data.text = str(directory / "runtime")
        settings = directory / "msamanda-settings.xml"
        tree.write(settings, encoding="utf-8", xml_declaration=True)
        return settings
