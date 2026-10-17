"""A local registry and reusable storage for completed downloads."""

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

DEFAULT_CACHE_DIR = Path(".interop_trace/cache")
_MARKER = ".interop-trace-cache"
_SIGNATURE = "interop-trace download cache v1\n"


@dataclass(frozen=True)
class Download:
    """A registered file and the source metadata recorded when it was fetched."""

    url: str
    path: Path
    size_bytes: int
    downloaded_at: str
    metadata: dict[str, str | None]

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
        downloader: Callable[[str, Path], dict[str, str | None]],
    ) -> Download:
        """Reuse a completed file or download and register it after success.

        ``downloader`` writes the requested bytes to the supplied path and returns
        source metadata. Exceptions leave no completed file or registry entry.
        """
        self._managed(create=True)
        directory = self._directory(url)
        cached = self._read(directory)
        if cached is not None and cached.available:
            return cached
        pending = self.root / "pending"
        pending.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=pending) as temporary:
            staging = Path(temporary)
            metadata = downloader(url, staging / "content")
            record = self._record(url, directory, staging, metadata)
            if directory.exists():
                shutil.rmtree(directory)
            directory.parent.mkdir(exist_ok=True)
            staging.replace(directory)
        return record

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

    def _directory(self, url: str) -> Path:
        key = hashlib.sha256(url.encode()).hexdigest()
        return self.root / "objects" / key

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
            return Download(
                url=data["url"],
                path=directory / "content",
                size_bytes=data["size_bytes"],
                downloaded_at=data["downloaded_at"],
                metadata=data["metadata"],
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _record(
        self,
        url: str,
        directory: Path,
        staging: Path,
        metadata: dict[str, str | None],
    ) -> Download:
        size = (staging / "content").stat().st_size
        if size == 0:
            raise ValueError("Cannot register an empty download.")
        timestamp = datetime.now(UTC).isoformat()
        data = {
            "url": url,
            "path": str(directory / "content"),
            "size_bytes": size,
            "downloaded_at": timestamp,
            "metadata": metadata,
        }
        (staging / "download.json").write_text(json.dumps(data, indent=2) + "\n")
        return Download(url, directory / "content", size, timestamp, metadata)
