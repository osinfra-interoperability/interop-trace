"""Check UniProt requests and transfer handling without network access."""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from interop_trace.databases import UniProtProvider


class Response(BytesIO):
    """A small HTTP response body with the headers used by the provider."""

    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        super().__init__(body)
        self.headers = headers


@pytest.mark.parametrize("format", ["fasta", "xml"])
def test_download_passes_query_and_records_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, format: str
) -> None:
    body = b">protein\nSEQUENCE\n" if format == "fasta" else b"<uniprot/>\n"
    response = Response(
        body,
        {"X-UniProt-Release": "test_release", "X-UniProt-Release-Date": "test_date"},
    )
    opener = Mock(return_value=response)
    monkeypatch.setattr("interop_trace.databases.uniprot.urlopen", opener)
    query = "accession:P69905 OR accession:P68871"
    output = tmp_path / "database"

    database = UniProtProvider(query=query, format=format).prepare(output_dir=output)

    request = opener.call_args.args[0]
    assert urlparse(request.full_url).path == "/uniprotkb/stream"
    assert parse_qs(urlparse(request.full_url).query) == {
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
    assert record["url"] == request.full_url
    assert {path.name for path in output.iterdir()} == {"database", "uniprot.json"}


def test_http_error_is_propagated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = HTTPError("https://rest.uniprot.org/", 400, "invalid query", {}, None)
    monkeypatch.setattr(
        "interop_trace.databases.uniprot.urlopen", Mock(side_effect=error)
    )
    output = tmp_path / "failed"

    with pytest.raises(HTTPError) as caught:
        UniProtProvider(query="invalid query").prepare(output_dir=output)

    assert caught.value is error
    assert list(output.iterdir()) == []


@pytest.mark.parametrize("body, expected", [(b"partial", "100"), (b"", "0")])
def test_incomplete_or_empty_download_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes, expected: str
) -> None:
    response = Response(body, {"Content-Length": expected})
    monkeypatch.setattr(
        "interop_trace.databases.uniprot.urlopen", Mock(return_value=response)
    )
    output = tmp_path / "failed"

    with pytest.raises((OSError, ValueError)):
        UniProtProvider(query="accession:P69905").prepare(output_dir=output)

    assert list(output.iterdir()) == []


def test_interrupted_download_removes_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = Response(b"", {})
    response.read = Mock(side_effect=[b"partial bytes", TimeoutError("interrupted")])
    monkeypatch.setattr(
        "interop_trace.databases.uniprot.urlopen", Mock(return_value=response)
    )
    output = tmp_path / "failed"

    with pytest.raises(TimeoutError):
        UniProtProvider(query="accession:P69905").prepare(output_dir=output)

    assert list(output.iterdir()) == []


def test_existing_download_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    previous = output / "database"
    previous.write_bytes(b"existing database")
    opener = Mock()
    monkeypatch.setattr("interop_trace.databases.uniprot.urlopen", opener)

    with pytest.raises(FileExistsError):
        UniProtProvider(query="accession:P69905").prepare(output_dir=output)

    assert previous.read_bytes() == b"existing database"
    opener.assert_not_called()


def test_missing_release_is_recorded_as_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "interop_trace.databases.uniprot.urlopen",
        Mock(return_value=Response(b">protein\nSEQUENCE\n", {})),
    )
    output = tmp_path / "database"

    UniProtProvider(query="accession:P69905").prepare(output_dir=output)

    record = json.loads((output / "uniprot.json").read_text())
    assert record["release"] is None
