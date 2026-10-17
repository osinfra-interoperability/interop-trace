"""A local registry and reusable storage for completed downloads."""

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pooch

DEFAULT_CACHE_DIR = Path(".interop_trace/cache")
_MARKER = ".interop-trace-cache"
_SIGNATURE = "interop-trace download cache v1\n"


def _download_http(
    url: str, destination: Path, metadata_headers: Mapping[str, str]
) -> dict[str, str | None]:
    metadata: dict[str, str | None] = {}

    def capture_headers(response: Any, **_: Any) -> None:
        metadata.update(
            {
                key: response.headers.get(header)
                for key, header in metadata_headers.items()
            }
        )

    pooch.HTTPDownloader(
        timeout=60,
        headers={"User-Agent": "interop-trace"},
        hooks={"response": capture_headers},
    )(url, str(destination), None)
    return metadata


@dataclass(frozen=True)
class Download:
    """A registered file and the source metadata recorded when it was fetched."""

    url: str
    path: Path
    size_bytes: int
    downloaded_at: str
    metadata: dict[str, str | None]
    name: str | None = None
    kind: str | None = None

    @property
    def available(self) -> bool:
        """Whether the local file still exists with its recorded size."""
        try:
            return self.path.is_file() and self.path.stat().st_size == self.size_bytes
        except OSError:
            return False


class DownloadCache:
    """Store downloads by exact request URL in a dedicated, owned directory."""

    def __init__(self, root: Path = DEFAULT_CACHE_DIR) -> None:
        self.root = root.resolve()

    def fetch(
        self,
        url: str,
        *,
        name: str | None = None,
        kind: str | None = None,
        metadata: Mapping[str, str | None] | None = None,
        metadata_headers: Mapping[str, str] | None = None,
    ) -> Download:
        """Reuse a completed file or download and register it after success.

        Pooch handles HTTP transfers and temporary files. ``metadata`` supplies
        known source information; ``metadata_headers`` maps record fields to
        response headers captured during that same transfer. Missing headers are
        recorded as ``None``. Cache hits preserve the original metadata. ``name``
        and ``kind`` label the component; older entries gain missing labels on reuse.
        """
        self._managed(create=True)
        directory = self.root / "objects" / hashlib.sha256(url.encode()).hexdigest()
        cached = self._read(directory)
        if cached is not None and cached.available:
            labeled = replace(
                cached, name=cached.name or name, kind=cached.kind or kind
            )
            if labeled != cached:
                self._write(labeled)
            return labeled
        if directory.exists():
            shutil.rmtree(directory)
        source_metadata = dict(metadata or {})

        def transfer(url: str, destination: str, _pooch: pooch.Pooch | None) -> None:
            path = Path(destination)
            source_metadata.update(_download_http(url, path, metadata_headers or {}))
            if path.stat().st_size == 0:
                raise ValueError("Cannot register an empty download.")

        # Providers do not supply an expected content checksum.
        pooch.retrieve(
            url, known_hash=None, path=directory, fname="content", downloader=transfer
        )
        path = directory / "content"
        return self._write(
            Download(
                url,
                path,
                path.stat().st_size,
                datetime.now(UTC).isoformat(),
                source_metadata,
                name,
                kind,
            )
        )

    def entries(self) -> list[Download]:
        """List registered downloads, including files that are now missing."""
        if not self._managed():
            return []
        return [
            entry
            for path in sorted((self.root / "objects").glob("*/download.json"))
            if (entry := self._read(path.parent)) is not None
        ]

    def clear(self) -> None:
        """Delete stored content and its registry, preserving the parent folder.

        Only this cache's managed ``objects`` and ``pending`` directories are
        removed. Call between workflow runs, when cached files are no longer in use.
        """
        if self._managed():
            for name in ("objects", "pending"):
                path = self.root / name
                if path.exists():
                    shutil.rmtree(path)

    def _managed(self, *, create: bool = False) -> bool:
        if not self.root.exists():
            if not create:
                return False
            self.root.mkdir(parents=True)
        marker = self.root / _MARKER
        if marker.is_file() and marker.read_text() == _SIGNATURE:
            return True
        if any(self.root.iterdir()):
            raise ValueError(f"Not an interop-trace cache directory: {self.root}")
        if create:
            marker.write_text(_SIGNATURE)
        return create

    def _read(self, directory: Path) -> Download | None:
        try:
            data = json.loads((directory / "download.json").read_text())
            data["path"] = directory / "content"
            return Download(**data)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write(self, record: Download) -> Download:
        (record.path.parent / "download.json").write_text(
            json.dumps(asdict(record), default=str, indent=2) + "\n"
        )
        return record
