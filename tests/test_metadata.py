"""Collect public metadata without live requests or changing its contents."""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from requests import Response
from typer.testing import CliRunner

from interop_trace.downloads import DownloadCache
from interop_trace.interfaces.cli import app
from interop_trace.metadata import snapshot_biotools


def test_snapshot_preserves_response_and_cached_provenance(
    tmp_path: Path, http_transport: Mock, http_response: Callable[..., Response]
) -> None:
    body = b'{ "biotoolsID": "Sage-proteomics", "unknown_field": null }\n'
    http_transport.side_effect = [http_response(body)]
    cache = DownloadCache(tmp_path / "cache")
    first = snapshot_biotools(
        "Sage-proteomics", output_dir=tmp_path / "first", cache=cache
    )
    source = json.loads((first / "source.json").read_text())
    assert source == {
        "source": "bio.tools",
        "biotools_id": "Sage-proteomics",
        "url": "https://bio.tools/api/tool/Sage-proteomics?format=json",
        "retrieved_at": cache.entries()[0].downloaded_at,
        "response": "entry.json",
    }
    assert datetime.fromisoformat(source["retrieved_at"]).tzinfo is not None
    assert cache.entries()[0].kind == "metadata"
    second = snapshot_biotools(
        "Sage-proteomics", output_dir=tmp_path / "second", cache=cache
    )
    cache.clear()
    with pytest.raises(FileExistsError):
        snapshot_biotools("Sage-proteomics", output_dir=first, cache=cache)
    http_transport.assert_called_once()
    assert http_transport.call_args.args[0].url == source["url"]
    for directory in (first, second):
        assert (directory / "entry.json").read_bytes() == body
        assert json.loads((directory / "source.json").read_text()) == source


@pytest.mark.parametrize("status", [404, 503])
def test_collection_failure_is_not_reported_as_a_snapshot(
    tmp_path: Path,
    status: int,
    http_transport: Mock,
    http_response: Callable[..., Response],
) -> None:
    http_transport.side_effect = [http_response(b"unavailable", status=status)]
    output = tmp_path / "snapshot"
    result = CliRunner().invoke(
        app,
        [
            "metadata",
            "biotools",
            "Sage-proteomics",
            "--output",
            str(output),
            "--cache-directory",
            str(tmp_path / "cache"),
        ],
    )
    assert result.exit_code == 1
    assert str(status) in result.output
    assert not (output / "entry.json").exists()
    assert not (output / "source.json").exists()
