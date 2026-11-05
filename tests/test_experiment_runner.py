"""Exercise YAML, cache, process and reporting boundaries without real downloads."""

import csv
import errno
import json
import subprocess
import sys
import tarfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from click import unstyle
from requests import Response
from typer.testing import CliRunner

from interop_trace.classification import assess_run
from interop_trace.evaluation import EvaluationResult, ProteoBenchDDA
from interop_trace.experiments import (
    create_run,
    execute_run,
    load_configuration,
    run_experiments,
)
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
    document = yaml.safe_load(pipeline.read_text())
    for choice in document["experiments"]:
        choice["acceptance"] = {"nr_feature": {"min": 3}}
    pipeline.write_text(yaml.safe_dump(document))
    configuration = load_configuration(pipeline)
    http_transport.assert_not_called()
    create_run(configuration, output_dir=output, cache_dir=tmp_path / "cache")
    http_transport.assert_not_called()
    with (output / "experiments.csv").open() as stream:
        assert [row["status"] for row in csv.DictReader(stream)] == ["not_started"] * 2
    assert not (output / "environment.json").exists()
    pipeline.write_text("changed after creation")
    results = execute_run(output)
    with pytest.raises(ValueError, match="already started"):
        execute_run(output)
    with (output / "experiments.csv").open() as stream:
        assert [row["status"] for row in csv.DictReader(stream)] == ["finished"] * 2
    assert len(assess_run(output)) == 2
    assert assess_run(output) == []
    with (output / "experiments.csv").open() as stream:
        assert [row["assessment_outcome"] for row in csv.DictReader(stream)] == [
            "unknown"
        ] * 2
    assert not results.failed
    evaluations = results.completed.values()
    assert [result.metrics["nr_feature"] for result in evaluations] == [3, 3]
    assert all(result.metrics["mean_abs_epsilon_global"] == 0 for result in evaluations)
    assert http_transport.call_count == 9  # catalogue, six measurements, FASTA, Sage
    snapshot = json.loads((output / "configuration.json").read_text())
    pipeline.write_text("changed after execution")
    assert "experiments:" in snapshot["files"][str(pipeline)]
    assert [choice["id"] for choice in snapshot["experiments"]] == ["first", "second"]
    for name in ("first", "second"):
        record = json.loads((output / name / "experiment.json").read_text())
        assert record["acceptance"] == {"nr_feature": {"min": 3}}
        assert record["status"] == "finished"
        assert "error" not in record
        assert record["started_at"] <= record["finished_at"]
        assert record["evaluation"]["metrics"]["nr_feature"] == 3
        assert record["database"]["path"]
        assert (
            output / name / "workflow/version.txt"
        ).read_text().strip() == "sage test-tool"
        assert (output / name / "evaluation/proteobench.json").is_file()


@pytest.mark.parametrize(
    "stage,error",
    [
        ("setup:database", PermissionError(errno.EACCES, "deliberate failure")),
        ("workflow", subprocess.CalledProcessError(2, ["test-tool"])),
        ("evaluation", RuntimeError("deliberate failure")),
        ("setup:database", KeyboardInterrupt("deliberate failure")),
        ("workflow", KeyboardInterrupt("deliberate failure")),
        ("evaluation", KeyboardInterrupt("deliberate failure")),
    ],
)
def test_errors_continue_but_interruptions_stop_the_batch(
    pipeline: Path,
    tmp_path: Path,
    stage: str,
    error: BaseException,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
) -> None:
    monkeypatch.setattr(
        ProteoBenchDDA, "evaluate", lambda *a, **k: EvaluationResult({"test_metric": 1})
    )
    if stage == "setup:database":
        from interop_trace.databases import UniProtProvider

        component, method = UniProtProvider, "setup"
    elif stage == "workflow":
        component, method = SageWorkflow, "run"
    else:
        component, method = ProteoBenchDDA, "evaluate"
    original = getattr(component, method)
    calls = 0

    def fail_first(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert (output / "environment.json").is_file()
            if "output_dir" in kwargs:
                folder = kwargs["output_dir"]
                folder.mkdir()
                (folder / "partial.log").write_text("partial evidence")
            error.add_note("Component test context")
            raise error from ValueError("underlying failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(component, method, fail_first)
    output = tmp_path / "failed"
    if isinstance(error, KeyboardInterrupt):
        with pytest.raises(KeyboardInterrupt, match="deliberate failure"):
            run_experiments(
                load_configuration(pipeline),
                output_dir=output,
                cache_dir=tmp_path / "cache",
            )
        second = json.loads((output / "second/experiment.json").read_text())
        assert second["status"] == "not_started" and "started_at" not in second
        assert not (output / "summary.json").exists()
    else:
        results = run_experiments(
            load_configuration(pipeline),
            output_dir=output,
            cache_dir=tmp_path / "cache",
        )
        assert list(results.completed) == ["second"]
        assert results.failed == {"first": f"{type(error).__name__}: {error}"}
        summary = json.loads((output / "summary.json").read_text())
        assert summary == {"completed": ["second"], "failed": results.failed}
        second = json.loads((output / "second/experiment.json").read_text())
        assert second["status"] == "finished"
    record = json.loads((output / "first/experiment.json").read_text())
    assert (output / "environment.json").is_file()
    assert record["status"] == "finished"
    assert record["stage"] == stage
    assert record["error"]["type"] == type(error).__name__
    assert record["error"]["module"] == type(error).__module__
    assert "ValueError: underlying failure\n" in record["error"]["traceback"]
    assert record["error"]["traceback"].endswith("Component test context\n")
    if isinstance(error, PermissionError):
        assert record["error"]["errno"] == errno.EACCES
        assert record["error"]["errno_name"] == "EACCES"
    if isinstance(error, subprocess.CalledProcessError):
        assert record["error"]["returncode"] == 2
    snapshot = json.loads((output / "configuration.json").read_text())
    assert [choice["id"] for choice in snapshot["experiments"]] == ["first", "second"]
    assert record["finished_at"]
    if stage == "setup:database":
        assert not (output / "first/dataset").exists()
    else:
        folder = "workflow" if stage == "workflow" else "evaluation"
        assert (
            output / "first" / folder / "partial.log"
        ).read_text() == "partial evidence"
    if stage != "evaluation":
        assert not (output / "first/evaluation").exists()
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
    pipeline: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
) -> None:
    release = Mock(return_value="test-release")
    monkeypatch.setattr("interop_trace.experiments.runner.platform.release", release)
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
            "--prepare-only",
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
    http_transport.assert_not_called()
    result = CliRunner().invoke(app, ["execute", str(output)])
    assert result.exit_code == 0, result.output
    assert "Finished 2 experiment(s), 0 with errors" in result.output
    assert json.loads((output / "environment.json").read_text()) == {
        "operating_system": "Darwin",
        "os_release": "test-release",
        "architecture": "arm64",
        "python_version": sys.version.split()[0],
    }
    release.assert_called_once_with()
    snapshot = json.loads((output / "configuration.json").read_text())
    assert [choice["id"] for choice in snapshot["experiments"]] == ["second", "first"]
    assert snapshot["sources"] == [str(other), str(pipeline)]
    for name in ("first", "second"):
        record = json.loads((output / name / "experiment.json").read_text())
        assert record["status"] == "finished"


@pytest.mark.parametrize("failed_ids", [("first",), ("second",), ("first", "second")])
def test_cli_summarizes_all_experiments_before_exiting_nonzero(
    pipeline: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_ids: tuple[str, ...],
) -> None:
    def evaluate(self, result, dataset, database, *, output_dir):
        if output_dir.parent.name in failed_ids:
            raise ValueError("cannot evaluate")
        return EvaluationResult({"test_metric": 1})

    monkeypatch.setattr(ProteoBenchDDA, "evaluate", evaluate)
    output = tmp_path / "batch"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "--all",
            "--directory",
            str(pipeline.parent),
            "--output",
            str(output),
            "--cache-directory",
            str(tmp_path / "cache"),
        ],
    )
    assert result.exit_code == 1, result.output
    assert f"Finished 2 experiment(s), {len(failed_ids)} with errors" in result.output
    for name in ("first", "second"):
        record = json.loads((output / name / "experiment.json").read_text())
        assert record["status"] == "finished"
        assert ("error" in record) == (name in failed_ids)
        assert (
            f"Error {name}: ValueError: cannot evaluate"
            if name in failed_ids
            else f"Without recorded errors: {name}"
        ) in result.output


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
    assert message in unstyle(result.output)
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
