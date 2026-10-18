"""Exercise YAML, cache, process and reporting boundaries without real downloads."""

import json
import sys
import tarfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from requests import Response
from typer.testing import CliRunner

from interop_trace.evaluation import EvaluationResult, ProteoBenchDDA
from interop_trace.experiments import load_configuration, run_experiments
from interop_trace.interfaces.cli import app
from interop_trace.workflows import SageWorkflow


def _sage_archive(url: str) -> bytes:
    """A runnable test tool emitting a small native-format LFQ table."""
    script = (
        f"#!{sys.executable}\n"
        + """
import csv, json, sys
from pathlib import Path
if sys.argv[1:] == ['--version']:
    print('sage test-tool')
    sys.exit(0)
args = sys.argv[1:]
output = Path(args[args.index('--output_directory') + 1])
names = args[-6:]
with (output / 'lfq.tsv').open('w') as stream:
    writer = csv.writer(stream, delimiter='\\t')
    writer.writerow(['peptide', 'charge', 'proteins', *names])
    for sequence, species, intensity in [
        ('PEPTIDEK', 'HUMAN', 100), ('AGLVVK', 'YEAST', 200), ('SPEPTIDER', 'ECOLI', 25)
    ]:
        writer.writerow([
            sequence, 2, 'sp|TEST|PROTEIN_' + species,
            *([intensity] * 3), *([100] * 3)
        ])
parameters = {
    'version': 'sage test-tool',
    'quant': {'lfq': True, 'lfq_settings': {'combine_charge_states': False}}
}
(output / 'results.json').write_text(json.dumps(parameters))
"""
    )
    name = url.rsplit("/", 1)[1].removesuffix(".tar.gz")
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for filename, content in {
            "sage": script,
            "LICENSE": "license",
            "README.md": "readme",
        }.items():
            data = content.encode()
            member = tarfile.TarInfo(f"{name}/{filename}")
            member.size, member.mode = len(data), 0o755
            archive.addfile(member, BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def pipeline(
    tmp_path: Path,
    http_transport: Mock,
    http_response: Callable[..., Response],
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    files = [
        f"LFQ_Orbitrap_DDA_Condition_{condition}_Sample_Alpha_{i:02}.mzML"
        for condition in ("A", "B")
        for i in range(1, 4)
    ]
    definitions = {
        "datasets": {
            "type": "pride",
            "parameters": {"project": "PXDTEST", "files": files},
        },
        "databases": {"type": "uniprot", "parameters": {"query": "accession:P69905"}},
        "workflows": {
            "type": "sage",
            "parameters": {"configuration": "../settings.json"},
        },
        "benchmarks": {"type": "proteobench_dda"},
    }
    folder = tmp_path / "components"
    folder.mkdir()
    for layer, definition in definitions.items():
        (folder / f"{layer}.yaml").write_text(yaml.safe_dump({"selected": definition}))
    (tmp_path / "settings.json").write_text('{"quant": {"lfq": true}}')
    choice = {
        "dataset": "selected",
        "database": "selected",
        "workflow": "selected",
        "benchmark": "selected",
    }
    document = {
        "components": {layer: f"components/{layer}.yaml" for layer in definitions},
        "experiments": [{"id": name, **choice} for name in ("first", "second")],
    }
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(document))
    catalogue = [
        {
            "fileName": name,
            "accession": name,
            "publicFileLocations": [{"value": f"https://example.org/{name}"}],
        }
        for name in files
    ]

    def send(request: Any) -> Response:
        if request.url.endswith("files/all"):
            return http_response(json.dumps(catalogue).encode())
        if "github.com" in request.url:
            return http_response(_sage_archive(request.url))
        if "uniprot.org" in request.url:
            return http_response(
                b">PROTEIN_HUMAN\nPEPTIDEK\n", {"X-UniProt-Release": "test-release"}
            )
        return http_response(b"tiny placeholder measurement")

    monkeypatch.setattr(
        "interop_trace.workflows.sage.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr(
        "interop_trace.workflows.sage.platform.machine", lambda: "arm64"
    )
    http_transport.side_effect = send
    return path


def test_two_experiments_share_downloads_and_use_real_scoring(
    pipeline: Path, tmp_path: Path, http_transport: Mock
) -> None:
    pytest.importorskip("proteobench")
    output = tmp_path / "results"
    configuration = load_configuration(pipeline)
    http_transport.assert_not_called()
    evaluations = run_experiments(
        configuration, output_dir=output, cache_dir=tmp_path / "cache"
    )
    assert [result.metrics["nr_feature"] for result in evaluations] == [3, 3]
    assert all(result.metrics["mean_abs_epsilon_global"] == 0 for result in evaluations)
    assert http_transport.call_count == 9  # catalogue, six measurements, FASTA, Sage
    snapshot = json.loads((output / "configuration.json").read_text())
    pipeline.write_text("changed after execution")
    assert "experiments:" in snapshot["files"][str(pipeline)]
    assert [choice["id"] for choice in snapshot["experiments"]] == ["first", "second"]
    for name in ("first", "second"):
        record = json.loads((output / name / "experiment.json").read_text())
        assert record["status"] == "completed"
        assert record["started_at"] <= record["finished_at"]
        assert record["evaluation"]["metrics"]["nr_feature"] == 3
        assert record["database"]["path"]
        assert (
            output / name / "workflow/version.txt"
        ).read_text().strip() == "sage test-tool"
        assert (output / name / "evaluation/proteobench.json").is_file()


@pytest.mark.parametrize("stage", ["setup:database", "workflow", "evaluation"])
@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
def test_failure_records_stage_and_does_not_start_later_experiment(
    pipeline: Path,
    tmp_path: Path,
    stage: str,
    error_type: type[BaseException],
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise error_type("deliberate failure")

    if stage == "setup:database":
        from interop_trace.databases import UniProtProvider

        monkeypatch.setattr(UniProtProvider, "setup", fail)
    elif stage == "workflow":
        monkeypatch.setattr(SageWorkflow, "run", fail)
    else:
        monkeypatch.setattr(ProteoBenchDDA, "evaluate", fail)
    output = tmp_path / "failed"
    with pytest.raises(error_type, match="deliberate failure"):
        run_experiments(
            load_configuration(pipeline),
            output_dir=output,
            cache_dir=tmp_path / "cache",
        )
    record = json.loads((output / "first/experiment.json").read_text())
    assert record["status"] == "failed"
    assert record["stage"] == stage
    assert record["error"]["type"] == error_type.__name__
    snapshot = json.loads((output / "configuration.json").read_text())
    assert [choice["id"] for choice in snapshot["experiments"]] == ["first", "second"]
    assert record["finished_at"]
    assert not (output / "second").exists()
    if stage == "evaluation":
        assert (output / "first/workflow/lfq.tsv").is_file()
        assert record["workflow"]["files"]["lfq.tsv"]


def test_existing_run_is_preserved_before_setup(
    pipeline: Path, tmp_path: Path, http_transport: Mock
) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    previous = output / "configuration.json"
    previous.write_text("previous run")
    with pytest.raises(FileExistsError):
        run_experiments(load_configuration(pipeline), output_dir=output)
    assert previous.read_text() == "previous run"
    http_transport.assert_not_called()


def test_cli_check_does_not_set_up_components(
    pipeline: Path, tmp_path: Path, http_transport: Mock
) -> None:
    output = tmp_path / "not-created"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--all",
            "--directory",
            str(pipeline.parent),
            "--check",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "2 experiment(s)" in result.output
    assert not output.exists()
    http_transport.assert_not_called()


def test_cli_executes_run(
    pipeline: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = yaml.safe_load(pipeline.read_text())
    other = pipeline.with_name("other.yml")
    other.write_text(
        yaml.safe_dump({**document, "experiments": document["experiments"][1:]})
    )
    document["experiments"] = document["experiments"][:1]
    pipeline.write_text(yaml.safe_dump(document))
    monkeypatch.setattr(
        ProteoBenchDDA, "evaluate", lambda *a, **k: EvaluationResult({"test_metric": 1})
    )
    output = tmp_path / "cli-results"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "second",
            "first",
            "--directory",
            str(pipeline.parent),
            "--output",
            str(output),
            "--cache-directory",
            str(tmp_path / "cache"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Completed 2 experiment(s)" in result.output
    snapshot = json.loads((output / "configuration.json").read_text())
    assert [choice["id"] for choice in snapshot["experiments"]] == ["second", "first"]
    assert snapshot["sources"] == [str(other), str(pipeline)]
    for name in ("first", "second"):
        record = json.loads((output / name / "experiment.json").read_text())
        assert record["status"] == "completed"


def test_cli_rejects_missing_benchmark_before_execution(
    pipeline: Path, tmp_path: Path, http_transport: Mock
) -> None:
    document = yaml.safe_load(pipeline.read_text())
    del document["experiments"][0]["benchmark"]
    pipeline.write_text(yaml.safe_dump(document))
    output = tmp_path / "invalid"
    result = CliRunner().invoke(
        app,
        ["run", "first", "--directory", str(pipeline.parent), "--output", str(output)],
    )
    assert result.exit_code == 1
    assert "benchmark" in result.output
    assert not output.exists()
    http_transport.assert_not_called()


@pytest.mark.parametrize(
    "arguments, message",
    [
        ([], "Provide experiment IDs or --all"),
        (["first", "--all"], "Provide experiment IDs or --all"),
        (["missing"], "Unknown experiment IDs"),
        (["first", "first"], "unique experiment IDs"),
    ],
)
def test_cli_rejects_invalid_selections_without_execution(
    pipeline: Path, arguments: list[str], message: str, http_transport: Mock
) -> None:
    result = CliRunner().invoke(
        app, ["run", *arguments, "--directory", str(pipeline.parent), "--check"]
    )
    assert result.exit_code != 0
    assert message in result.output
    http_transport.assert_not_called()


def test_cli_lists_available_ids_without_setup(
    pipeline: Path, http_transport: Mock
) -> None:
    result = CliRunner().invoke(
        app, ["experiments", "--directory", str(pipeline.parent)]
    )
    assert result.exit_code == 0, result.output
    assert "first | run.yaml" in result.output
    assert "second | run.yaml" in result.output
    http_transport.assert_not_called()
