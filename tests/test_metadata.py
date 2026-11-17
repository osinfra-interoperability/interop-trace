"""Collect public metadata without live requests or changing its contents."""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from requests import Response
from typer.testing import CliRunner

from interop_trace.downloads import DownloadCache
from interop_trace.edam import OLS_EDAM_URL, term_url
from interop_trace.experiments import create_run, load_experiments
from interop_trace.interfaces.cli import app
from interop_trace.metadata import collect_run_metadata, snapshot_biotools


def test_snapshot_formats_response_and_preserves_cached_provenance(
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
        saved = (directory / "entry.json").read_text()
        assert json.loads(saved) == json.loads(body)
        assert saved == (
            '{\n  "biotoolsID": "Sage-proteomics",\n  "unknown_field": null\n}\n'
        )
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


def test_run_collection_uses_saved_selection_and_shared_snapshots(
    configuration: Path,
    tmp_path: Path,
    edam_path: Path,
    http_transport: Mock,
    http_response: Callable[..., Response],
) -> None:
    for layer, identifier in (
        ("datasets", "pride"),
        ("databases", "uniprotkb"),
        ("workflows", "Sage-proteomics"),
    ):
        path = configuration.parent / f"components/{layer}.yaml"
        definition = yaml.safe_load(path.read_text())
        definition["selected"]["metadata"] = {"biotools": identifier}
        path.write_text(yaml.safe_dump(definition))
    document = yaml.safe_load(configuration.read_text())
    choice = document["experiments"][0]
    document["experiments"].append({**choice, "id": "second"})
    configuration.write_text(yaml.safe_dump(document))
    run = tmp_path / "run"
    create_run(
        load_experiments(configuration.parent, ["first", "second"]),
        output_dir=run,
        cache_dir=tmp_path / "cache",
    )
    http_transport.assert_not_called()
    configuration.write_text("changed after run creation")
    before = {
        name: (run / name / "experiment.json").read_bytes()
        for name in ("first", "second")
    }

    def respond(request):
        if request.url == OLS_EDAM_URL:
            return http_response(b'{"config":{"version":"test-release"}}')
        if request.url == term_url("http://edamontology.org/data_2976"):
            response = next(
                row
                for row in json.loads(edam_path.read_text())
                if row["iri"].endswith("data_2976")
            )
            return http_response(json.dumps(response).encode())
        assert request.url.startswith("https://bio.tools/")
        identifier = request.url.split("/")[-1].split("?")[0]
        return http_response(
            json.dumps(
                {
                    "biotoolsID": identifier,
                    "function": [
                        {
                            "input": [
                                {"data": {"uri": "http://edamontology.org/data_2976"}}
                            ]
                        }
                    ],
                }
            ).encode()
        )

    http_transport.side_effect = respond
    index = json.loads(collect_run_metadata(run).read_text())
    rows = index["components"]
    assert len(rows) == 6 and http_transport.call_count == 5
    assert index["ontology"]["status"] == "collected"
    requests = index["ontology"]["requests"]
    assert len(requests) == 2
    cached = {e.url: e for e in DownloadCache(tmp_path / "cache").entries()}
    for request in requests:
        assert request["retrieved_at"] == cached[request["url"]].downloaded_at
        assert json.loads(
            (run / "metadata" / request["response"]).read_text()
        ) == json.loads(cached[request["url"]].path.read_text())
    assert not list((run / "metadata").rglob("*.owl"))
    assert {row["experiment"] for row in rows} == {"first", "second"}
    assert all(
        row["status"] == "collected" and row["profile"] == "selected" for row in rows
    )
    assert [row["directory"] for row in rows[:3]] == [
        row["directory"] for row in rows[3:]
    ]
    for row in rows:
        entry = run / "metadata" / row["directory"] / "entry.json"
        assert json.loads(entry.read_text())["biotoolsID"] == row["biotools_id"]
    with pytest.raises(FileExistsError):
        collect_run_metadata(run)
    assert {
        name: (run / name / "experiment.json").read_bytes() for name in before
    } == before


@pytest.mark.parametrize(
    "status,expected", [(404, "not_found"), (503, "retrieval_failed")]
)
def test_run_collection_records_unavailable_metadata_and_continues(
    configuration: Path,
    tmp_path: Path,
    status: int,
    expected: str,
    http_transport: Mock,
    http_response: Callable[..., Response],
) -> None:
    for layer, identifier in (
        ("databases", "missing"),
        ("workflows", "Sage-proteomics"),
    ):
        path = configuration.parent / f"components/{layer}.yaml"
        definition = yaml.safe_load(path.read_text())
        definition["selected"]["metadata"] = {"biotools": identifier}
        path.write_text(yaml.safe_dump(definition))
    run = tmp_path / "run"
    create_run(
        load_experiments(configuration.parent),
        output_dir=run,
        cache_dir=tmp_path / "cache",
    )
    http_transport.side_effect = [
        http_response(b"unavailable", status=status),
        http_response(
            b'{"function":[{"input":[{"data":{"uri":"http://edamontology.org/data_2976"}}]}]}'
        ),
        http_response(b"ontology unavailable", status=503),
        http_response(b"term unavailable", status=503),
    ]
    result = CliRunner().invoke(app, ["metadata", "collect", str(run)])
    assert result.exit_code == 1
    rows = json.loads((run / "metadata/index.json").read_text())["components"]
    assert [row["status"] for row in rows] == [
        "missing_reference",
        expected,
        "collected",
    ]
    assert rows[0]["biotools_id"] is None
    assert rows[1]["error"]["http_status"] == status
    assert rows[1]["error"]["type"] == "HTTPError"
    assert (run / "metadata" / rows[2]["directory"] / "source.json").is_file()
    ontology = json.loads((run / "metadata/index.json").read_text())["ontology"]
    assert ontology["status"] == "retrieval_failed"
    assert all(row["error"]["http_status"] == 503 for row in ontology["requests"])
    assert http_transport.call_count == 4
