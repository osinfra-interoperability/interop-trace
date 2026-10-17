"""Retrieve working database files from the UniProtKB REST API."""

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from interop_trace.databases.base import Database
from interop_trace.downloads import DEFAULT_CACHE_DIR, DownloadCache


@dataclass(frozen=True)
class UniProtProvider:
    """A UniProtKB query and native export format, interpreted by UniProt.

    ``prepare`` reuses downloaded content from ``cache_dir`` and writes a release
    record in the requested output directory. The database points to the cached
    file, so preparation creates no duplicate copy of the database.
    """

    query: str
    format: str = "fasta"
    cache_dir: Path = DEFAULT_CACHE_DIR

    def prepare(self, *, output_dir: Path) -> Database:
        """Retrieve or reuse a database and record its original source release.

        UniProt validates the query and requested export format. HTTP and transfer
        errors propagate; incomplete downloads are not cached. ``output_dir``
        must be new and holds metadata only. Clear the download cache between
        runs to fetch a fresh response for the same query.
        """
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        url = "https://rest.uniprot.org/uniprotkb/stream?" + urlencode(
            {"query": self.query, "format": self.format, "compressed": "false"}
        )
        download = DownloadCache(self.cache_dir).fetch(
            url,
            name="uniprot",
            kind="database",
            metadata_headers={
                "release": "X-UniProt-Release",
                "release_date": "X-UniProt-Release-Date",
            },
        )
        record = {
            "query": self.query,
            "format": self.format,
            "url": url,
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
