"""Check the single-file provider's lifecycle, provenance and cache reuse."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.datasets import HttpDatasetProvider
from interop_trace.downloads import DownloadCache


def test_setup_reuses_file_and_prepare_preserves_source(
    tmp_path: Path, http_transport: Mock
) -> None:
    url = "https://example.org/reference.mzML"
    provider = HttpDatasetProvider(url, "reference.mzML")
    with pytest.raises(RuntimeError, match="setup"):
        provider.prepare(output_dir=tmp_path / "too-early")
    http_transport.assert_not_called()
    cache = DownloadCache(tmp_path / "cache")
    provider.setup(cache=cache)
    first = provider.prepare(output_dir=tmp_path / "first")
    provider.setup(cache=cache)
    second = provider.prepare(output_dir=tmp_path / "second")
    http_transport.assert_called_once()
    assert first == second
    assert first.files[0].name == "reference.mzML"
    assert first.files[0].is_absolute()
    record = json.loads((tmp_path / "first/http.json").read_text())
    assert record["url"] == url
    assert record["name"] == "http" and record["kind"] == "dataset"
    assert record["path"] == str(first.files[0])
    assert (tmp_path / "first/http.json").read_bytes() == (
        tmp_path / "second/http.json"
    ).read_bytes()


def test_existing_output_and_invalid_filename_do_not_overwrite(
    tmp_path: Path, http_transport: Mock
) -> None:
    provider = HttpDatasetProvider("https://example.org/input", "../outside")
    with pytest.raises(ValueError, match="basename"):
        provider.setup(cache=DownloadCache(tmp_path / "cache"))
    http_transport.assert_not_called()
    provider = HttpDatasetProvider("https://example.org/input", "input.mzML")
    provider.setup(cache=DownloadCache(tmp_path / "cache"))
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        provider.prepare(output_dir=output)
    assert not list(output.iterdir())
