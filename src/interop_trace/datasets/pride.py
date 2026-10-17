"""Retrieve explicitly selected files from a public PRIDE project."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from interop_trace.datasets.base import Dataset
from interop_trace.datasets.registry import registry
from interop_trace.downloads import Download, DownloadCache


@registry.register(
    "pride",
    summary="Selected public PRIDE measurements",
    documentation="components.md#pride",
)
@dataclass
class PrideProvider:
    """A public project accession and exact filenames to use as measurements.

    ``setup`` resolves files in the shared cache with their native names. ``prepare``
    writes a provenance record; it does not convert files or infer sample metadata.
    """

    project: str
    files: tuple[str, ...]
    _catalogue: Download | None = field(default=None, init=False, repr=False)
    _selected: list[dict[str, Any]] = field(
        default_factory=list, init=False, repr=False
    )
    _downloads: list[Download] = field(default_factory=list, init=False, repr=False)

    def setup(self, *, cache: DownloadCache) -> None:
        """Resolve the catalogue and all selections, then fetch or reuse files.

        Resolve every filename and URL before measurement downloads. Cache hits
        preserve original source records. Failed setup leaves the component unready.
        """
        self._catalogue = None
        if not self.files or len(set(self.files)) != len(self.files):
            raise ValueError("Select at least one PRIDE file, without duplicate names.")
        url = (
            "https://www.ebi.ac.uk/pride/ws/archive/v3/projects/"
            f"{quote(self.project, safe='')}/files/all"
        )
        catalogue = cache.fetch(
            url,
            name="pride",
            kind="dataset",
            filename="files.json",
            metadata={"project": self.project, "role": "file_catalogue"},
        )
        selected = _select_files(json.loads(catalogue.path.read_bytes()), self.files)
        downloads = _download_files(cache, self.project, selected)
        self._catalogue, self._selected, self._downloads = (
            catalogue,
            selected,
            downloads,
        )

    def prepare(self, *, output_dir: Path) -> Dataset:
        """Return resolved measurements and write provenance in a new directory."""
        if self._catalogue is None:
            raise RuntimeError("Call PrideProvider.setup(cache=...) before prepare().")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        record = {
            "project": self.project,
            "catalogue": asdict(self._catalogue),
            "files": [
                {"source": source, "download": asdict(download)}
                for source, download in zip(
                    self._selected, self._downloads, strict=True
                )
            ],
        }
        (output_dir / "pride.json").write_text(
            json.dumps(record, default=str, indent=2) + "\n", encoding="utf-8"
        )
        return Dataset(files=tuple(download.path for download in self._downloads))


def _select_files(
    catalogue: list[dict[str, Any]], names: tuple[str, ...]
) -> list[dict[str, Any]]:
    selected = []
    for name in names:
        matches = [file for file in catalogue if file["fileName"] == name]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one PRIDE file named {name!r}; found {len(matches)}."
            )
        selected.append(matches[0])
    return selected


def _download_url(file: dict[str, Any]) -> str:
    urls = [str(location["value"]) for location in file["publicFileLocations"]]
    for prefix in ("https://", "http://", "ftp://ftp.pride.ebi.ac.uk/"):
        for url in urls:
            if url.startswith(prefix):
                return url.replace("ftp://", "https://", 1)
    raise ValueError(f"No HTTP download location for PRIDE file {file['fileName']!r}.")


def _download_files(
    cache: DownloadCache, project: str, selected: list[dict[str, Any]]
) -> list[Download]:
    urls = [_download_url(file) for file in selected]
    return [
        cache.fetch(
            url,
            name="pride",
            kind="dataset",
            filename=file["fileName"],
            metadata={
                "project": project,
                "file_accession": file["accession"],
                "checksum": file.get("checksum") or None,
            },
        )
        for file, url in zip(selected, urls, strict=True)
    ]
