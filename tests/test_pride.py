"""Check PRIDE selection, provenance and reuse through the shared HTTP cache."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from requests import Response
from requests.exceptions import HTTPError

from interop_trace.datasets import PrideProvider
from interop_trace.downloads import DownloadCache

CATALOGUE_URL = "https://www.ebi.ac.uk/pride/ws/archive/v3/projects/PXD000001/files/all"
FILE_BASE = "ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/"


@pytest.fixture
def catalogue() -> list[dict[str, Any]]:
    return [
        {
            "fileName": name,
            "accession": f"file-id-{name}",
            "checksum": "f" * 32,
            "fileSizeBytes": len(b"measurements"),
            "updatedDate": "2024-01-01T00:00:00.000+00:00",
            "publicFileLocations": [
                {"name": "FTP Protocol", "value": f"ftp://{FILE_BASE}{name}"}
            ],
        }
        for name in ("first.mzML", "second.mzML", "unselected.raw")
    ]


@pytest.fixture
def pride_http(
    catalogue: list[dict[str, Any]],
    http_transport: Mock,
    http_response: Callable[..., Response],
) -> Mock:
    def send(request: Any) -> Response:
        if request.url == CATALOGUE_URL:
            return http_response(json.dumps(catalogue).encode())
        return http_response(b"measurements")

    http_transport.side_effect = send
    return http_transport


def test_selected_files_keep_names_order_and_source_provenance(
    tmp_path: Path, pride_http: Mock, catalogue: list[dict[str, Any]]
) -> None:
    output = tmp_path / "run"
    dataset = PrideProvider(
        project="PXD000001",
        files=("second.mzML", "first.mzML"),
        cache_dir=tmp_path / "cache",
    ).prepare(output_dir=output)

    assert [path.name for path in dataset.files] == ["second.mzML", "first.mzML"]
    assert all(path.is_absolute() for path in dataset.files)
    assert all(path.read_bytes() == b"measurements" for path in dataset.files)
    assert dataset.sample_metadata is None
    assert list(output.iterdir()) == [output / "pride.json"]
    assert [call.args[0].url for call in pride_http.call_args_list] == [
        CATALOGUE_URL,
        f"https://{FILE_BASE}second.mzML",
        f"https://{FILE_BASE}first.mzML",
    ]
    record = json.loads((output / "pride.json").read_text())
    assert record["project"] == "PXD000001"
    assert record["catalogue"]["url"] == CATALOGUE_URL
    assert record["catalogue"]["downloaded_at"]
    assert record["files"][0]["source"] == catalogue[1]
    download = record["files"][0]["download"]
    assert download["path"] == str(dataset.files[0])
    assert download["metadata"]["checksum"] == "f" * 32
    assert download["metadata"]["file_accession"] == "file-id-second.mzML"
    assert download["downloaded_at"]
    entries = DownloadCache(tmp_path / "cache").entries()
    assert len(entries) == 3
    assert all(entry.name == "pride" and entry.kind == "dataset" for entry in entries)


def test_repeated_preparation_reuses_catalogue_files_and_provenance(
    tmp_path: Path, pride_http: Mock
) -> None:
    provider = PrideProvider("PXD000001", ("first.mzML",), cache_dir=tmp_path / "cache")
    first = provider.prepare(output_dir=tmp_path / "first")
    second = provider.prepare(output_dir=tmp_path / "second")

    assert pride_http.call_count == 2
    assert first == second
    assert (tmp_path / "first/pride.json").read_bytes() == (
        tmp_path / "second/pride.json"
    ).read_bytes()


@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_ambiguous_name_fails_before_any_measurement_download(
    tmp_path: Path,
    pride_http: Mock,
    catalogue: list[dict[str, Any]],
    duplicate: bool,
) -> None:
    if duplicate:
        catalogue.append(dict(catalogue[0]))
    name = "first.mzML" if duplicate else "missing.mzML"
    provider = PrideProvider(
        "PXD000001", ("second.mzML", name), cache_dir=tmp_path / "cache"
    )

    with pytest.raises(ValueError, match="Expected one PRIDE file"):
        provider.prepare(output_dir=tmp_path / "run")

    pride_http.assert_called_once()
    assert pride_http.call_args.args[0].url == CATALOGUE_URL
    assert list((tmp_path / "run").iterdir()) == []


def test_unsupported_location_fails_before_any_measurement_download(
    tmp_path: Path, pride_http: Mock, catalogue: list[dict[str, Any]]
) -> None:
    catalogue[0]["publicFileLocations"] = [{"value": "user@fasp.example.org:file"}]
    provider = PrideProvider(
        "PXD000001", ("second.mzML", "first.mzML"), cache_dir=tmp_path / "cache"
    )

    with pytest.raises(ValueError, match="No HTTP download location"):
        provider.prepare(output_dir=tmp_path / "run")

    pride_http.assert_called_once()
    assert list((tmp_path / "run").iterdir()) == []


@pytest.mark.parametrize("scheme", ["https", "http"])
def test_published_http_location_is_preferred_over_ftp_mirror(
    tmp_path: Path, pride_http: Mock, catalogue: list[dict[str, Any]], scheme: str
) -> None:
    url = f"{scheme}://example.org/first.mzML"
    catalogue[0]["publicFileLocations"].append({"value": url})

    PrideProvider("PXD000001", ("first.mzML",), cache_dir=tmp_path / "cache").prepare(
        output_dir=tmp_path / "run"
    )

    assert pride_http.call_args.args[0].url == url


def test_failed_file_can_be_retried_without_redownloading_completed_files(
    tmp_path: Path, pride_http: Mock, http_response: Callable[..., Response]
) -> None:
    send = pride_http.side_effect

    def fail_second(request: Any) -> Response:
        if request.url.endswith("second.mzML"):
            return http_response(b"unavailable", status=503)
        return send(request)

    pride_http.side_effect = fail_second
    provider = PrideProvider(
        "PXD000001", ("first.mzML", "second.mzML"), cache_dir=tmp_path / "cache"
    )
    with pytest.raises(HTTPError):
        provider.prepare(output_dir=tmp_path / "failed")
    assert list((tmp_path / "failed").iterdir()) == []
    assert len(DownloadCache(provider.cache_dir).entries()) == 2

    pride_http.side_effect = send
    dataset = provider.prepare(output_dir=tmp_path / "retry")

    assert pride_http.call_count == 4
    assert len(dataset.files) == 2
    assert all(path.is_file() for path in dataset.files)


def test_catalogue_http_error_is_propagated(
    tmp_path: Path, pride_http: Mock, http_response: Callable[..., Response]
) -> None:
    pride_http.side_effect = [http_response(b"not found", status=404)]

    with pytest.raises(HTTPError):
        PrideProvider(
            "PXD000001", ("first.mzML",), cache_dir=tmp_path / "cache"
        ).prepare(output_dir=tmp_path / "failed")

    assert list((tmp_path / "failed").iterdir()) == []
    assert DownloadCache(tmp_path / "cache").entries() == []


@pytest.mark.parametrize("files", [(), ("first.mzML", "first.mzML")])
def test_empty_or_duplicate_selection_fails_without_requests(
    tmp_path: Path, pride_http: Mock, files: tuple[str, ...]
) -> None:
    with pytest.raises(ValueError, match="at least one PRIDE file"):
        PrideProvider("PXD000001", files, cache_dir=tmp_path / "cache").prepare(
            output_dir=tmp_path / "run"
        )

    pride_http.assert_not_called()
    assert not (tmp_path / "run").exists()


def test_existing_output_directory_is_preserved(
    tmp_path: Path, pride_http: Mock
) -> None:
    output = tmp_path / "run"
    output.mkdir()
    metadata = output / "pride.json"
    metadata.write_text("previous run")

    with pytest.raises(FileExistsError):
        PrideProvider(
            "PXD000001", ("first.mzML",), cache_dir=tmp_path / "cache"
        ).prepare(output_dir=output)

    pride_http.assert_not_called()
    assert metadata.read_text() == "previous run"


def test_clear_forces_fresh_catalogue_and_file_downloads(
    tmp_path: Path, pride_http: Mock
) -> None:
    provider = PrideProvider("PXD000001", ("first.mzML",), cache_dir=tmp_path / "cache")
    provider.prepare(output_dir=tmp_path / "first")
    original = (tmp_path / "first/pride.json").read_bytes()

    DownloadCache(provider.cache_dir).clear()
    provider.prepare(output_dir=tmp_path / "second")

    assert pride_http.call_count == 4
    assert (tmp_path / "first/pride.json").read_bytes() == original
