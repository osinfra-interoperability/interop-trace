"""Check cache reuse, registry accuracy, failure cleanup and deletion scope."""

import gzip
import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest
from requests import Response
from requests.exceptions import HTTPError, RequestException

from interop_trace.downloads import DownloadCache


def test_matching_request_reuses_download_and_metadata(
    tmp_path: Path, http_transport: Mock
) -> None:
    cache = DownloadCache(tmp_path / "cache")

    first = cache.fetch(
        "https://example.org/file", metadata={"release": "test_release"}
    )
    second = cache.fetch(
        "https://example.org/file", metadata={"release": "new_release"}
    )

    http_transport.assert_called_once()
    assert first == second
    assert first.available
    assert first.metadata == {"release": "test_release"}
    record = json.loads((first.path.parent / "download.json").read_text())
    assert record["path"] == str(first.path)
    assert cache.entries() == [first]


def test_different_requests_get_separate_entries(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    first = cache.fetch("https://example.org/file?format=fasta")
    second = cache.fetch("https://example.org/file?format=xml")

    assert first.path != second.path
    assert len(cache.entries()) == 2


@pytest.mark.parametrize("changed", [False, True])
def test_missing_or_size_changed_file_is_downloaded_again(
    tmp_path: Path, changed: bool, http_transport: Mock
) -> None:
    cache = DownloadCache(tmp_path / "cache")
    first = cache.fetch("https://example.org/file")
    if changed:
        first.path.write_bytes(b"truncated")
    else:
        first.path.unlink()

    assert not cache.entries()[0].available
    second = cache.fetch("https://example.org/file")

    assert http_transport.call_count == 2
    assert second.available
    assert second.path.read_bytes() == b"https://example.org/file"


@pytest.mark.parametrize("fails", [False, True])
def test_failed_or_empty_download_is_not_registered(
    tmp_path: Path,
    fails: bool,
    http_transport: Mock,
    http_response: Callable[..., Response],
) -> None:
    cache = DownloadCache(tmp_path / "cache")
    body = b"x" * 2048 if fails else b""
    http_transport.side_effect = [
        http_response(body, {"Content-Length": str(2 * len(body))}),
        http_response(b"recovered"),
    ]

    with pytest.raises((RequestException, ValueError)):
        cache.fetch("https://example.org/file")

    assert cache.entries() == []
    assert not any(path.is_file() for path in (cache.root / "objects").rglob("*"))
    assert cache.fetch("https://example.org/file").available


def test_clear_removes_only_managed_downloads(tmp_path: Path) -> None:
    results = tmp_path / "results.json"
    results.write_text("keep these results")
    cache = DownloadCache(tmp_path / "cache")
    entry = cache.fetch("https://example.org/file")
    registry = entry.path.parent / "download.json"
    record = json.loads(registry.read_text())
    record["path"] = str(results)
    registry.write_text(json.dumps(record))
    (cache.root / "pending" / "interrupted").mkdir(parents=True)
    (cache.root / "pending" / "interrupted" / "content").write_bytes(b"partial")

    cache.clear()

    assert not entry.path.exists()
    assert not (cache.root / "pending").exists()
    assert cache.entries() == []
    assert results.read_text() == "keep these results"
    assert cache.fetch("https://example.org/file").available


def test_unmanaged_directory_cannot_be_cleared_or_used(tmp_path: Path) -> None:
    existing = tmp_path / "important.txt"
    existing.write_text("keep me")
    cache = DownloadCache(tmp_path)

    with pytest.raises(ValueError, match="Not an interop-trace cache"):
        cache.clear()
    with pytest.raises(ValueError, match="Not an interop-trace cache"):
        cache.fetch("https://example.org/file")

    assert existing.read_text() == "keep me"


def test_missing_cache_is_not_created_by_inspection_or_clear(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")

    assert cache.entries() == []
    cache.clear()

    assert not cache.root.exists()


def test_invalid_registry_is_replaced_on_next_download(
    tmp_path: Path, http_transport: Mock
) -> None:
    cache = DownloadCache(tmp_path / "cache")
    entry = cache.fetch("https://example.org/file")
    (entry.path.parent / "download.json").write_text("broken json")
    http_transport.reset_mock()

    recovered = cache.fetch("https://example.org/file")

    http_transport.assert_called_once()
    assert recovered.available
    assert cache.entries() == [recovered]


def test_selected_response_headers_are_recorded_in_the_same_request(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    http_transport.side_effect = [
        http_response(b"content", {"x-release": "original", "Unrelated": "omit"})
    ]
    metadata = {"version": "requested"}
    entry = DownloadCache(tmp_path / "cache").fetch(
        "https://example.org/file",
        metadata=metadata,
        metadata_headers={"release": "X-Release", "release_date": "X-Release-Date"},
    )

    http_transport.assert_called_once()
    request = http_transport.call_args.args[0]
    assert request.method == "GET"
    assert request.headers["User-Agent"] == "interop-trace"
    assert entry.metadata == {
        "version": "requested",
        "release": "original",
        "release_date": None,
    }
    assert metadata == {"version": "requested"}


def test_redirect_records_headers_from_final_response(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    http_transport.side_effect = [
        http_response(b"", {"Location": "/final", "X-Release": "redirect"}, status=302),
        http_response(b"content", {"X-Release": "final"}),
    ]
    cache = DownloadCache(tmp_path / "cache")

    entry = cache.fetch(
        "https://example.org/file", metadata_headers={"release": "X-Release"}
    )

    assert entry.metadata == {"release": "final"}
    assert entry.path.read_bytes() == b"content"
    assert cache.fetch("https://example.org/file") == entry
    assert http_transport.call_count == 2


def test_http_failure_does_not_register_response_metadata(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    http_transport.side_effect = [
        http_response(b"error", {"X-Release": "not-a-download"}, status=400)
    ]
    cache = DownloadCache(tmp_path / "cache")

    with pytest.raises(HTTPError):
        cache.fetch(
            "https://example.org/file", metadata_headers={"release": "X-Release"}
        )

    assert cache.entries() == []
    assert not any(path.is_file() for path in (cache.root / "objects").rglob("*"))


def test_http_compression_uses_wire_length_without_rejecting_decoded_content(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    body = b">protein\nSEQUENCE\n" * 100
    compressed = gzip.compress(body)
    http_transport.side_effect = [
        http_response(
            compressed,
            {"Content-Encoding": "gzip", "Content-Length": str(len(compressed))},
        )
    ]

    entry = DownloadCache(tmp_path / "cache").fetch("https://example.org/file")

    assert entry.path.read_bytes() == body
    assert entry.size_bytes == len(body)
