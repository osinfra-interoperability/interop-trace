"""Check UniProt requests and transfer handling without network access."""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
from requests import Response
from requests.exceptions import ConnectionError, HTTPError, RequestException
from urllib3.exceptions import ReadTimeoutError

from interop_trace.databases import UniProtProvider


@pytest.mark.parametrize("format", ["fasta", "xml"])
def test_download_passes_query_and_records_release(
    tmp_path: Path,
    http_transport: Mock,
    http_response: Callable[..., Response],
    format: str,
) -> None:
    body = b">protein\nSEQUENCE\n" if format == "fasta" else b"<uniprot/>\n"
    http_transport.side_effect = [
        http_response(
            body,
            {
                "X-UniProt-Release": "test_release",
                "X-UniProt-Release-Date": "test_date",
            },
        )
    ]
    query = "accession:P69905 OR accession:P68871"
    output = tmp_path / "database"

    database = UniProtProvider(
        query=query, format=format, cache_dir=tmp_path / "cache"
    ).prepare(output_dir=output)

    http_transport.assert_called_once()
    request = http_transport.call_args.args[0]
    assert urlparse(request.url).path == "/uniprotkb/stream"
    assert parse_qs(urlparse(request.url).query) == {
        "query": [query],
        "format": [format],
        "compressed": ["false"],
    }
    assert database.path.is_absolute()
    assert database.path.read_bytes() == body
    assert database.format == ("fasta" if format == "fasta" else "uniprot_xml")
    record = json.loads((output / "uniprot.json").read_text())
    assert record["release"] == "test_release"
    assert record["release_date"] == "test_date"
    assert record["query"] == query
    assert record["url"] == request.url
    assert {path.name for path in output.iterdir()} == {"uniprot.json"}
    assert record["cache_path"] == str(database.path)
    assert not database.path.is_relative_to(output)


def test_http_error_is_propagated(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    http_transport.side_effect = [http_response(b"invalid query", status=400)]
    output = tmp_path / "failed"

    with pytest.raises(HTTPError) as caught:
        UniProtProvider(query="invalid query", cache_dir=tmp_path / "cache").prepare(
            output_dir=output
        )

    assert caught.value.response.status_code == 400
    assert list(output.iterdir()) == []


@pytest.mark.parametrize("body, expected", [(b"partial", "100"), (b"", "0")])
def test_incomplete_or_empty_download_is_not_published(
    tmp_path: Path,
    http_transport: Mock,
    http_response: Callable[..., Response],
    body: bytes,
    expected: str,
) -> None:
    http_transport.side_effect = [http_response(body, {"Content-Length": expected})]
    output = tmp_path / "failed"

    with pytest.raises((RequestException, ValueError)):
        UniProtProvider(query="accession:P69905", cache_dir=tmp_path / "cache").prepare(
            output_dir=output
        )

    assert list(output.iterdir()) == []


def test_interrupted_download_removes_partial_file(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    def interrupted() -> Iterator[bytes]:
        yield b"partial bytes"
        raise ReadTimeoutError(None, None, "interrupted")

    response = http_response(b"")
    response.raw.stream = Mock(return_value=interrupted())
    http_transport.side_effect = [response]
    output = tmp_path / "failed"

    with pytest.raises(ConnectionError):
        UniProtProvider(query="accession:P69905", cache_dir=tmp_path / "cache").prepare(
            output_dir=output
        )

    assert list(output.iterdir()) == []


def test_existing_download_is_preserved(tmp_path: Path, http_transport: Mock) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    previous = output / "database"
    previous.write_bytes(b"existing database")

    with pytest.raises(FileExistsError):
        UniProtProvider(query="accession:P69905", cache_dir=tmp_path / "cache").prepare(
            output_dir=output
        )

    assert previous.read_bytes() == b"existing database"
    http_transport.assert_not_called()


def test_missing_release_is_recorded_as_unknown(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    http_transport.side_effect = [http_response(b">protein\nSEQUENCE\n")]
    output = tmp_path / "database"

    UniProtProvider(query="accession:P69905", cache_dir=tmp_path / "cache").prepare(
        output_dir=output
    )

    record = json.loads((output / "uniprot.json").read_text())
    assert record["release"] is None


def test_repeated_preparation_reuses_download_and_original_release(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    http_transport.side_effect = [
        http_response(b">protein\nSEQUENCE\n", {"X-UniProt-Release": "original"})
    ]
    provider = UniProtProvider(query="accession:P69905", cache_dir=tmp_path / "cache")

    first = provider.prepare(output_dir=tmp_path / "first")
    second = provider.prepare(output_dir=tmp_path / "second")

    http_transport.assert_called_once()
    assert first.path == second.path
    assert first.path.read_bytes() == b">protein\nSEQUENCE\n"
    record = json.loads((tmp_path / "second/uniprot.json").read_text())
    assert record["release"] == "original"


def test_clear_forces_a_new_response_and_release(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    from interop_trace.downloads import DownloadCache

    http_transport.side_effect = [
        http_response(b">old\nSEQUENCE\n", {"X-UniProt-Release": "old"}),
        http_response(b">new\nSEQUENCE\n", {"X-UniProt-Release": "new"}),
    ]
    provider = UniProtProvider(query="accession:P69905", cache_dir=tmp_path / "cache")
    provider.prepare(output_dir=tmp_path / "first")

    DownloadCache(provider.cache_dir).clear()
    database = provider.prepare(output_dir=tmp_path / "second")

    assert http_transport.call_count == 2
    assert database.path.read_bytes() == b">new\nSEQUENCE\n"
    assert json.loads((tmp_path / "first/uniprot.json").read_text())["release"] == "old"
    assert (
        json.loads((tmp_path / "second/uniprot.json").read_text())["release"] == "new"
    )
