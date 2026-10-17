"""Retrieve explicitly selected files from a public PRIDE project."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from interop_trace.datasets.base import Dataset
from interop_trace.downloads import DEFAULT_CACHE_DIR, Download, DownloadCache


@dataclass(frozen=True)
class PrideProvider:
    """A public project accession and exact filenames to use as measurements.

    Files keep their native names and contents in the shared cache. ``prepare``
    writes a provenance record; it does not convert files or infer sample metadata.
    """

    project: str
    files: tuple[str, ...]
    cache_dir: Path = DEFAULT_CACHE_DIR

    def prepare(self, *, output_dir: Path) -> Dataset:
        """Prepare selected measurements and record their original source metadata.

        ``output_dir`` must be new. Resolve every requested name and download URL
        before fetching measurement files. Cached catalogues and files are reused
        until cleared or missing. Failures leave no completed provenance record.
        """
        if not self.files or len(set(self.files)) != len(self.files):
            raise ValueError("Select at least one PRIDE file, without duplicate names.")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        cache = DownloadCache(self.cache_dir)
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
        record = {
            "project": self.project,
            "catalogue": asdict(catalogue),
            "files": [
                {"source": source, "download": asdict(download)}
                for source, download in zip(selected, downloads, strict=True)
            ],
        }
        (output_dir / "pride.json").write_text(
            json.dumps(record, default=str, indent=2) + "\n", encoding="utf-8"
        )
        return Dataset(files=tuple(download.path for download in downloads))


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
