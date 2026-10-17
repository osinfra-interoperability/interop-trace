"""Exercise the installed ProteoBench calculations on tiny Sage-format tables."""

import csv
import json
import math
from importlib.metadata import version
from pathlib import Path
from unittest.mock import Mock

import pytest

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.evaluation import ProteoBenchDDA
from interop_trace.workflows import WorkflowResult

pytest.importorskip("proteobench")


@pytest.fixture
def rows() -> list[list[str | int]]:
    return [
        ["PEPTIDEK", 2, "sp|TEST1|PROTEIN_HUMAN", 100, 100, 100, 100, 100, 100],
        ["AGLVVK", 2, "sp|TEST2|PROTEIN_YEAST", 200, 200, 200, 100, 100, 100],
        ["SPEPTIDER", 2, "sp|TEST3|PROTEIN_ECOLI", 25, 25, 25, 100, 100, 100],
    ]


def _write_lfq(
    path: Path,
    dataset: Dataset,
    rows: list[list[str | int]],
    *,
    absolute: bool = False,
) -> None:
    names = [str(path) if absolute else path.name for path in dataset.files]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["peptide", "charge", "proteins", *names])
        writer.writerows(rows)


@pytest.fixture
def inputs(
    tmp_path: Path, rows: list[list[str | int]]
) -> tuple[Dataset, Database, WorkflowResult]:
    files = tuple(
        tmp_path / f"LFQ_Orbitrap_DDA_Condition_{condition}_Sample_Alpha_{i:02}.mzML"
        for condition in ("A", "B")
        for i in range(1, 4)
    )
    for path in files:
        path.write_text("placeholder; the evaluator reads LFQ outputs only")
    dataset = Dataset(files)
    fasta = tmp_path / "proteins.fasta"
    fasta.write_text("".join(f">{row[2]}\n{row[0]}\n" for row in rows))
    database = Database(fasta, format="fasta")
    parameters = tmp_path / "results.json"
    parameters.write_text('{"version": "sage-test", "quant": {"lfq": true}}')
    lfq = tmp_path / "lfq.tsv"
    _write_lfq(lfq, dataset, rows)
    return (
        dataset,
        database,
        WorkflowResult("sage", {"lfq.tsv": lfq, "results.json": parameters}),
    )


def test_expected_mixture_and_provenance(
    inputs: tuple[Dataset, Database, WorkflowResult],
    tmp_path: Path,
    http_transport: Mock,
) -> None:
    dataset, database, result = inputs
    output = tmp_path / "evaluation"
    evaluation = ProteoBenchDDA().evaluate(result, dataset, database, output_dir=output)

    assert evaluation.metrics["nr_feature"] == 3
    assert evaluation.metrics["mean_abs_epsilon_global"] == 0
    assert evaluation.metrics["CV_median"] == 0
    assert evaluation.metrics["roc_auc"] == 1
    assert all(path.is_absolute() and path.is_file() for path in evaluation.reports)
    record = json.loads((output / "proteobench.json").read_text())
    assert record["proteobench_version"] == version("proteobench")
    assert record["min_observations"] == 3
    assert record["dataset"]["files"] == [str(path) for path in dataset.files]
    assert record["database"]["path"] == str(database.path)
    assert record["workflow"]["files"]["lfq.tsv"] == str(result.files["lfq.tsv"])
    assert record["sage_parameters"]["quant"]["lfq"] is True
    assert record["metrics"] == evaluation.metrics
    assert (output / "module_settings.toml").is_file()
    assert (output / "parse_settings_sage.toml").is_file()
    with (output / "ions.tsv").open() as stream:
        ions = list(csv.DictReader(stream, delimiter="\t"))
    assert len(ions) == 3
    assert {ion["species"]: float(ion["log2_A_vs_B"]) for ion in ions} == {
        "HUMAN": 0,
        "YEAST": 1,
        "ECOLI": -2,
    }
    http_transport.assert_not_called()


def test_incorrect_yeast_ratio_changes_accuracy(
    inputs: tuple[Dataset, Database, WorkflowResult],
    rows: list[list[str | int]],
    tmp_path: Path,
) -> None:
    dataset, database, result = inputs
    rows[1][3:] = [100] * 6
    _write_lfq(result.files["lfq.tsv"], dataset, rows)
    metrics = (
        ProteoBenchDDA()
        .evaluate(result, dataset, database, output_dir=tmp_path / "biased")
        .metrics
    )

    assert metrics["mean_abs_epsilon_YEAST"] == 1
    assert metrics["mean_abs_epsilon_eq_species"] == pytest.approx(1 / 3)


def test_observation_threshold_counts_all_six_runs(
    inputs: tuple[Dataset, Database, WorkflowResult],
    rows: list[list[str | int]],
    tmp_path: Path,
) -> None:
    dataset, database, result = inputs
    rows[1][3:5] = [0, 0]
    _write_lfq(result.files["lfq.tsv"], dataset, rows)
    default = ProteoBenchDDA().evaluate(
        result, dataset, database, output_dir=tmp_path / "three"
    )
    strict = ProteoBenchDDA(min_observations=6).evaluate(
        result, dataset, database, output_dir=tmp_path / "six"
    )

    assert default.metrics["nr_feature"] == 3
    assert strict.metrics["nr_feature"] == 2


def test_undefined_metrics_are_explicit(
    inputs: tuple[Dataset, Database, WorkflowResult],
    rows: list[list[str | int]],
    tmp_path: Path,
) -> None:
    dataset, database, result = inputs
    _write_lfq(result.files["lfq.tsv"], dataset, rows[:1])
    output = tmp_path / "human-only"
    evaluation = ProteoBenchDDA().evaluate(result, dataset, database, output_dir=output)

    assert "roc_auc" not in evaluation.metrics
    assert all(math.isfinite(value) for value in evaluation.metrics.values())
    record = json.loads((output / "proteobench.json").read_text())
    assert "roc_auc" in record["undefined_metrics"]
    assert "variance_epsilon_global" in record["undefined_metrics"]


@pytest.mark.parametrize("compressed", [False, True])
def test_absolute_lfq_headers(
    inputs: tuple[Dataset, Database, WorkflowResult],
    rows: list[list[str | int]],
    tmp_path: Path,
    compressed: bool,
) -> None:
    dataset, database, result = inputs
    if compressed:
        dataset = Dataset(
            tuple(path.rename(str(path) + ".gz") for path in dataset.files)
        )
    _write_lfq(result.files["lfq.tsv"], dataset, rows, absolute=True)
    evaluation = ProteoBenchDDA().evaluate(
        result, dataset, database, output_dir=tmp_path / "absolute"
    )

    assert evaluation.metrics["nr_feature"] == 3
    assert evaluation.metrics["mean_abs_epsilon_global"] == 0


def test_unrecognized_species_cannot_produce_a_success_report(
    inputs: tuple[Dataset, Database, WorkflowResult],
    rows: list[list[str | int]],
    tmp_path: Path,
) -> None:
    dataset, database, result = inputs
    for row in rows:
        row[2] = "unknown_protein"
    _write_lfq(result.files["lfq.tsv"], dataset, rows)
    output = tmp_path / "unrecognized"

    with pytest.raises(ValueError, match="No species-specific precursor ions"):
        ProteoBenchDDA().evaluate(result, dataset, database, output_dir=output)

    assert not (output / "proteobench.json").exists()


@pytest.mark.parametrize("threshold", [0, 7])
def test_invalid_observation_threshold(
    inputs: tuple[Dataset, Database, WorkflowResult], tmp_path: Path, threshold: int
) -> None:
    dataset, database, result = inputs
    output = tmp_path / "invalid"
    with pytest.raises(ValueError, match="between 1 and 6"):
        ProteoBenchDDA(threshold).evaluate(result, dataset, database, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize("files", [("other.mzML",), (), ("duplicate",) * 6])
def test_unrelated_or_incomplete_design_is_rejected(
    inputs: tuple[Dataset, Database, WorkflowResult],
    tmp_path: Path,
    files: tuple[str, ...],
) -> None:
    _, database, result = inputs
    dataset = Dataset(tuple(tmp_path / name for name in files))
    with pytest.raises(ValueError, match="six distinct published Q Exactive runs"):
        ProteoBenchDDA().evaluate(
            result, dataset, database, output_dir=tmp_path / "invalid"
        )


@pytest.mark.parametrize("missing", ["lfq.tsv", "results.json"])
def test_missing_sage_output(
    inputs: tuple[Dataset, Database, WorkflowResult], tmp_path: Path, missing: str
) -> None:
    dataset, database, result = inputs
    result = WorkflowResult(
        "sage", {k: v for k, v in result.files.items() if k != missing}
    )
    with pytest.raises(ValueError, match="requires Sage lfq.tsv and results.json"):
        ProteoBenchDDA().evaluate(
            result, dataset, database, output_dir=tmp_path / "invalid"
        )


def test_unsupported_result_format(
    inputs: tuple[Dataset, Database, WorkflowResult], tmp_path: Path
) -> None:
    dataset, database, _ = inputs
    with pytest.raises(ValueError, match="accepts Sage results only"):
        ProteoBenchDDA().evaluate(
            WorkflowResult("other", {}),
            dataset,
            database,
            output_dir=tmp_path / "invalid",
        )


def test_existing_evaluation_is_preserved(
    inputs: tuple[Dataset, Database, WorkflowResult], tmp_path: Path
) -> None:
    dataset, database, result = inputs
    output = tmp_path / "existing"
    output.mkdir()
    report = output / "proteobench.json"
    report.write_text("previous evaluation")
    with pytest.raises(FileExistsError):
        ProteoBenchDDA().evaluate(result, dataset, database, output_dir=output)
    assert report.read_text() == "previous evaluation"
