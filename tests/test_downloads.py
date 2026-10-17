"""Check cache reuse, registry accuracy, failure cleanup and deletion scope."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.downloads import DownloadCache


def download(url: str, destination: Path) -> dict[str, str | None]:
    destination.write_bytes(url.encode())
    return {"release": "test_release"}


def test_matching_request_reuses_download_and_metadata(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    downloader = Mock(side_effect=download)

    first = cache.fetch("https://example.org/file", downloader)
    second = cache.fetch("https://example.org/file", downloader)

    downloader.assert_called_once()
    assert first == second
    assert first.available
    assert first.metadata == {"release": "test_release"}
    record = json.loads((first.path.parent / "download.json").read_text())
    assert record["path"] == str(first.path)
    assert cache.entries() == [first]


def test_different_requests_get_separate_entries(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    first = cache.fetch("https://example.org/file?format=fasta", download)
    second = cache.fetch("https://example.org/file?format=xml", download)

    assert first.path != second.path
    assert len(cache.entries()) == 2


@pytest.mark.parametrize("changed", [False, True])
def test_missing_or_size_changed_file_is_downloaded_again(
    tmp_path: Path, changed: bool
) -> None:
    cache = DownloadCache(tmp_path / "cache")
    downloader = Mock(side_effect=download)
    first = cache.fetch("https://example.org/file", downloader)
    if changed:
        first.path.write_bytes(b"truncated")
    else:
        first.path.unlink()

    assert not cache.entries()[0].available
    second = cache.fetch("https://example.org/file", downloader)

    assert downloader.call_count == 2
    assert second.available
    assert second.path.read_bytes() == b"https://example.org/file"


@pytest.mark.parametrize("fails", [False, True])
def test_failed_or_empty_download_is_not_registered(
    tmp_path: Path, fails: bool
) -> None:
    cache = DownloadCache(tmp_path / "cache")

    def incomplete(url: str, destination: Path) -> dict[str, str | None]:
        destination.write_bytes(b"partial" if fails else b"")
        if fails:
            raise TimeoutError("interrupted")
        return {}

    with pytest.raises((TimeoutError, ValueError)):
        cache.fetch("https://example.org/file", incomplete)

    assert cache.entries() == []
    assert list((cache.root / "pending").iterdir()) == []


def test_clear_removes_only_managed_downloads(tmp_path: Path) -> None:
    results = tmp_path / "results.json"
    results.write_text("keep these results")
    cache = DownloadCache(tmp_path / "cache")
    entry = cache.fetch("https://example.org/file", download)
    registry = entry.path.parent / "download.json"
    record = json.loads(registry.read_text())
    record["path"] = str(results)
    registry.write_text(json.dumps(record))
    (cache.root / "pending" / "interrupted").mkdir()
    (cache.root / "pending" / "interrupted" / "content").write_bytes(b"partial")

    cache.clear()

    assert not entry.path.exists()
    assert not (cache.root / "pending").exists()
    assert cache.entries() == []
    assert results.read_text() == "keep these results"
    assert cache.fetch("https://example.org/file", download).available


def test_unmanaged_directory_cannot_be_cleared_or_used(tmp_path: Path) -> None:
    existing = tmp_path / "important.txt"
    existing.write_text("keep me")
    cache = DownloadCache(tmp_path)

    with pytest.raises(ValueError, match="Not an interop-trace cache"):
        cache.clear()
    with pytest.raises(ValueError, match="Not an interop-trace cache"):
        cache.fetch("https://example.org/file", download)

    assert existing.read_text() == "keep me"


def test_missing_cache_is_not_created_by_inspection_or_clear(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")

    assert cache.entries() == []
    cache.clear()

    assert not cache.root.exists()


def test_invalid_registry_is_replaced_on_next_download(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    entry = cache.fetch("https://example.org/file", download)
    (entry.path.parent / "download.json").write_text("broken json")
    downloader = Mock(side_effect=download)

    recovered = cache.fetch("https://example.org/file", downloader)

    downloader.assert_called_once()
    assert recovered.available
    assert cache.entries() == [recovered]
