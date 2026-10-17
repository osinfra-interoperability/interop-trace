"""Retrieve one explicitly named measurement file over HTTP."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from interop_trace.datasets.base import Dataset
from interop_trace.datasets.registry import registry
from interop_trace.downloads import Download, DownloadCache


@registry.register(
    "http",
    summary="A named measurement file from an HTTP URL",
    documentation="components.md#http",
)
@dataclass
class HttpDatasetProvider:
    """One measurement URL and its local filename; contents are not converted."""

    url: str
    filename: str
    _download: Download | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.startswith(
            ("https://", "http://")
        ):
            raise ValueError("Measurement URL must use HTTP or HTTPS.")

    def setup(self, *, cache: DownloadCache) -> None:
        """Fetch or reuse the selected file through the shared cache."""
        self._download = None
        self._download = cache.fetch(
            self.url, name="http", kind="dataset", filename=self.filename
        )

    def prepare(self, *, output_dir: Path) -> Dataset:
        """Return the resolved file and write its original download provenance."""
        if self._download is None:
            raise RuntimeError(
                "Call HttpDatasetProvider.setup(cache=...) before prepare()."
            )
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        (output_dir / "http.json").write_text(
            json.dumps(asdict(self._download), default=str, indent=2) + "\n",
            encoding="utf-8",
        )
        return Dataset((self._download.path,))
