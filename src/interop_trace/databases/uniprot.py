"""Retrieve working database files from the UniProtKB REST API."""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from interop_trace.databases.base import Database


@dataclass(frozen=True)
class UniProtProvider:
    """A UniProtKB query and native export format, interpreted by UniProt.

    ``prepare`` creates one working file and a release record in the requested
    directory. It maintains no separate cache or archive of downloaded files.
    """

    query: str
    format: str = "fasta"

    def prepare(self, *, output_dir: Path) -> Database:
        """Retrieve a database into a new directory and record its source release.

        UniProt validates the query and requested export format. HTTP and transfer
        errors propagate; incomplete working files are removed. The caller owns
        the working directory and can remove it after the workflow has used it.
        """
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        url = "https://rest.uniprot.org/uniprotkb/stream?" + urlencode(
            {"query": self.query, "format": self.format, "compressed": "false"}
        )
        partial = output_dir / "database.part"
        destination = output_dir / "database"
        try:
            release = self._download(url, partial)
            record = {"query": self.query, "format": self.format, "url": url, **release}
            (output_dir / "uniprot.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
        return Database(
            path=destination,
            format="fasta" if self.format == "fasta" else f"uniprot_{self.format}",
        )

    def _download(self, url: str, destination: Path) -> dict[str, str | None]:
        request = Request(url, headers={"User-Agent": "interop-trace"})
        with urlopen(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output, length=64 * 1024)
            size = output.tell()
            expected = response.headers.get("Content-Length")
            if expected is not None and size != int(expected):
                raise OSError("UniProt download ended before the expected length.")
            if size == 0:
                raise ValueError("UniProt returned an empty database.")
            return {
                "release": response.headers.get("X-UniProt-Release"),
                "release_date": response.headers.get("X-UniProt-Release-Date"),
            }
