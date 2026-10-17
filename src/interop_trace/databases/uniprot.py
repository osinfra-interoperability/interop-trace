"""Retrieve working database files from the UniProtKB REST API."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from interop_trace.databases.base import Database
from interop_trace.databases.registry import registry
from interop_trace.downloads import Download, DownloadCache


@registry.register(
    "uniprot",
    summary="Query-based UniProtKB exports",
    documentation="components.md#uniprot",
)
@dataclass
class UniProtProvider:
    """A UniProtKB query and native export format, interpreted by UniProt.

    ``setup`` resolves cached content. ``prepare`` writes its original release
    record and returns the cached database without duplicating it.
    """

    query: str
    format: str = "fasta"
    _download: Download | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("UniProt query must be a nonempty string.")
        if not isinstance(self.format, str) or not self.format.strip():
            raise ValueError("UniProt format must be a nonempty string.")

    def setup(self, *, cache: DownloadCache) -> None:
        """Fetch or reuse the query response and its original release metadata."""
        self._download = None
        url = "https://rest.uniprot.org/uniprotkb/stream?" + urlencode(
            {"query": self.query, "format": self.format, "compressed": "false"}
        )
        self._download = cache.fetch(
            url,
            name="uniprot",
            kind="database",
            metadata_headers={
                "release": "X-UniProt-Release",
                "release_date": "X-UniProt-Release-Date",
            },
        )

    def prepare(self, *, output_dir: Path) -> Database:
        """Return the resolved database and record its original source release.

        UniProt validates the query and requested export format. HTTP and transfer
        errors propagate; incomplete downloads are not cached. ``output_dir``
        must be new and holds metadata only. Clear the download cache between
        runs to fetch a fresh response for the same query.
        """
        download = self._download
        if download is None:
            raise RuntimeError(
                "Call UniProtProvider.setup(cache=...) before prepare()."
            )
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        record = {
            "query": self.query,
            "format": self.format,
            "url": download.url,
            "cache_path": str(download.path),
            "downloaded_at": download.downloaded_at,
            **download.metadata,
        }
        (output_dir / "uniprot.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        return Database(
            path=download.path,
            format="fasta" if self.format == "fasta" else f"uniprot_{self.format}",
        )
