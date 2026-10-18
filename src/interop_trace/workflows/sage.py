"""Run the Sage command-line tool with its native JSON configuration."""

import os
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pooch

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.downloads import DEFAULT_CACHE_DIR, DownloadCache
from interop_trace.workflows.base import WorkflowResult
from interop_trace.workflows.registry import registry


def download_sage(
    version: str = "0.14.7", *, cache_dir: Path = DEFAULT_CACHE_DIR
) -> Path:
    """Download a pinned Sage release once and return its cached executable.

    Select the published build for this operating system and CPU. Pooch reuses
    extracted files and restores missing ones from the cached archive. The shared
    cache records the release URL, version and original download time.
    """
    target = _sage_target()
    name = f"sage-v{version}-{target}"
    windows = target.endswith("windows-msvc")
    asset = name + (".zip" if windows else ".tar.gz")
    url = f"https://github.com/lazear/sage/releases/download/v{version}/{asset}"

    archive = DownloadCache(cache_dir).fetch(
        url, name="sage", kind="workflow", metadata={"version": version}
    )
    binary = "sage.exe" if windows else "sage"
    extractor = pooch.Unzip if windows else pooch.Untar
    extractor(
        members=[f"{name}/{file}" for file in (binary, "LICENSE", "README.md")],
        extract_dir="extracted",
    )(str(archive.path), "fetch", None)
    executable = archive.path.parent / "extracted" / name / binary
    if not executable.is_file():
        raise FileNotFoundError(f"Sage release does not contain {name}/{binary}")
    return executable


def _sage_target() -> str:
    system, machine = platform.system(), platform.machine().lower()
    machine = {"arm64": "aarch64", "amd64": "x86_64"}.get(machine, machine)
    targets = {
        ("Darwin", "aarch64"): "aarch64-apple-darwin",
        ("Darwin", "x86_64"): "x86_64-apple-darwin",
        ("Linux", "aarch64"): "aarch64-unknown-linux-musl",
        ("Linux", "x86_64"): "x86_64-unknown-linux-musl",
        ("Windows", "x86_64"): "x86_64-pc-windows-msvc",
    }
    try:
        return targets[system, machine]
    except KeyError:
        raise ValueError(f"No Sage download for {system}/{machine}.") from None


@registry.register(
    "sage",
    summary="Local proteomics search and LFQ",
    documentation="components.md#sage",
    paths=("configuration", "executable"),
)
@dataclass
class SageWorkflow:
    """A pinned Sage release or managed executable, with native search settings.

    ``setup`` resolves ``executable`` or downloads ``version`` through the cache.
    ``configuration`` is a native Sage JSON file, interpreted by Sage itself.
    """

    configuration: Path
    executable: Path | None = None
    threads: int = 2
    version: str = "0.14.7"
    _executable: Path | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.threads) is not int or self.threads < 1:
            raise ValueError("Sage threads must be a positive integer.")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("Sage version must be a nonempty string.")

    def setup(self, *, cache: DownloadCache) -> None:
        """Resolve a local executable or fetch and extract the pinned release."""
        self._executable = None
        executable = (
            self.executable.resolve()
            if self.executable is not None
            else download_sage(self.version, cache_dir=cache.root)
        )
        if not executable.is_file():
            raise FileNotFoundError(executable)
        self._executable = executable

    def run(
        self, dataset: Dataset, database: Database, *, output_dir: Path
    ) -> WorkflowResult:
        """Run Sage in a new directory and return its files, log and version.

        The explicit inputs override paths in the configuration. An empty dataset
        is rejected to prevent Sage from using configuration inputs instead.
        Relative configuration references resolve beside the configuration file.
        Sage errors propagate as ``subprocess.CalledProcessError``; files already
        written remain available for inspection. Existing output directories are
        never reused. Database format labels and file extensions are not checked.
        """
        if self._executable is None:
            raise RuntimeError("Call SageWorkflow.setup(cache=...) before run().")
        if not dataset.files:
            raise ValueError("SageWorkflow requires at least one measurement file.")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        configuration = self.configuration.resolve()
        self._execute(
            [str(self._executable), "--version"],
            output_dir / "version.txt",
            configuration.parent,
        )
        self._execute(
            self._command(dataset, database, output_dir),
            output_dir / "sage.log",
            configuration.parent,
        )
        return WorkflowResult(
            format="sage",
            files={
                str(path.relative_to(output_dir)): path
                for path in sorted(output_dir.rglob("*"))
                if path.is_file()
            },
        )

    def _command(
        self, dataset: Dataset, database: Database, output_dir: Path
    ) -> list[str]:
        return [
            str(self._executable),
            str(self.configuration.resolve()),
            "--disable-telemetry-i-dont-want-to-improve-sage",
            "--fasta",
            str(database.path.resolve()),
            "--output_directory",
            str(output_dir),
            *[str(path.resolve()) for path in dataset.files],
        ]

    def _execute(self, command: list[str], log_path: Path, cwd: Path) -> None:
        with log_path.open("w") as log:
            subprocess.run(
                command,
                cwd=cwd,
                env={**os.environ, "RAYON_NUM_THREADS": str(self.threads)},
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
