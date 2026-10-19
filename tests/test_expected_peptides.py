"""Check reference recovery without treating every other peptide as incorrect."""

import json
from pathlib import Path

import pytest

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.evaluation import ExpectedPeptides
from interop_trace.workflows import WorkflowResult


def test_target_rank_confidence_and_duplicate_matches(tmp_path: Path) -> None:
    source = tmp_path / "results.sage.tsv"
    source.write_text(
        "peptide\trank\tlabel\tspectrum_q\n"
        "FIRST\t1\t1\t0.01\n"
        "FIRST\t1\t1\t0.005\n"
        "SECOND\t1\t1\t1\n"
        "DECOY\t1\t-1\t0\n"
        "RUNNERUP\t2\t1\t0\n"
        "UNLISTED\t1\t1\t0\n"
    )
    benchmark = ExpectedPeptides(("FIRST", "SECOND", "DECOY", "RUNNERUP", "ABSENT"))
    result = benchmark.evaluate(
        WorkflowResult("sage", {source.name: source}),
        Dataset(()),
        Database(tmp_path / "unused.fasta", "fasta"),
        output_dir=tmp_path / "evaluation",
    )
    assert result.metrics == {
        "expected_peptides": 5,
        "matched_expected_peptides": 2,
        "expected_recovery": 0.4,
        "matched_expected_peptides_at_threshold": 1,
        "expected_recovery_at_threshold": 0.2,
    }
    report = json.loads(result.reports[0].read_text())
    assert report["matched"] == ["FIRST", "SECOND"]
    assert report["matched_at_threshold"] == ["FIRST"]
    assert report["missing_at_threshold"] == ["ABSENT", "DECOY", "RUNNERUP", "SECOND"]
    with pytest.raises(FileExistsError):
        benchmark.evaluate(
            WorkflowResult("sage", {source.name: source}),
            Dataset(()),
            Database(tmp_path / "unused.fasta", "fasta"),
            output_dir=tmp_path / "evaluation",
        )


@pytest.mark.parametrize(
    "table",
    [
        "peptide\nFIRST\n",
        "peptide\trank\tlabel\tspectrum_q\nFIRST\t1\t1\tnan\n",
        "peptide\trank\tlabel\tspectrum_q\nFIRST\t1\t1\t-1\n",
    ],
)
def test_invalid_table_cannot_be_reported_as_zero_recovery(
    tmp_path: Path, table: str
) -> None:
    source = tmp_path / "results.sage.tsv"
    source.write_text(table)
    with pytest.raises(ValueError):
        ExpectedPeptides(("FIRST",)).evaluate(
            WorkflowResult("sage", {source.name: source}),
            Dataset(()),
            Database(tmp_path / "unused.fasta", "fasta"),
            output_dir=tmp_path / "evaluation",
        )
    assert not (tmp_path / "evaluation").exists()


@pytest.mark.parametrize("peptides", [(), ("",), ("A", "A"), "PEPTIDE"])
def test_reference_must_be_explicit_and_nonempty(peptides: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="peptides"):
        ExpectedPeptides(peptides)


@pytest.mark.parametrize("threshold", [float("nan"), -0.1, 1.1, True, "0.01"])
def test_invalid_threshold_is_rejected(threshold: float) -> None:
    with pytest.raises(ValueError, match="max_q_value"):
        ExpectedPeptides(("PEPTIDE",), max_q_value=threshold)


@pytest.mark.parametrize(
    "format, filename, header, decoy",
    [
        ("comet", "001.comet.txt", "plain_peptide\tnum\tprotein", "DECOY_"),
        ("msamanda", "001.msamanda.csv", "Sequence\tRank\tProtein Accessions", "REV_"),
    ],
)
def test_native_recovery_uses_top_target_sequences_without_inventing_q_values(
    tmp_path: Path, format: str, filename: str, header: str, decoy: str
) -> None:
    source = tmp_path / filename
    source.write_text(
        ("CometVersion test\n" if format == "comet" else "# MS Amanda test\n")
        + header
        + "\nFIRST\t1\tprotein\nFIRST\t1\tprotein\nSECOND\t2\tprotein\n"
        + f"DECOY\t1\t{decoy}protein\nUNLISTED\t1\tprotein\n"
    )
    inputs = (
        WorkflowResult(format, {filename: source}),
        Dataset(()),
        Database(tmp_path / "unused.fasta", "fasta"),
    )
    benchmark = ExpectedPeptides(
        ("FIRST", "SECOND", "DECOY"), max_q_value=None, sequence_only=True
    )
    result = benchmark.evaluate(*inputs, output_dir=tmp_path / "evaluation")
    assert result.metrics == {
        "expected_peptides": 3,
        "matched_expected_peptides": 1,
        "expected_recovery": 1 / 3,
    }
    report = json.loads(result.reports[0].read_text())
    assert report["confidence_filter"] == "none"
    assert report["matched"] == ["FIRST"]
    assert report["missing"] == ["DECOY", "SECOND"]
    with pytest.raises(ValueError, match="native scores are not spectrum q-values"):
        ExpectedPeptides(("FIRST",), sequence_only=True).evaluate(
            *inputs, output_dir=tmp_path / "invalid"
        )
    source.write_text("wrong columns\n")
    with pytest.raises(ValueError, match="table must contain"):
        benchmark.evaluate(*inputs, output_dir=tmp_path / "malformed")
    assert not (tmp_path / "malformed").exists()


def test_sage_sequence_matching_ignores_modifications_explicitly(
    tmp_path: Path,
) -> None:
    source = tmp_path / "results.sage.tsv"
    source.write_text(
        "peptide\trank\tlabel\tspectrum_q\n[+229.16293]-PEPTIDEK[+229.16293]\t1\t1\t0.005\n"
    )
    result = ExpectedPeptides(("PEPTIDEK",), sequence_only=True).evaluate(
        WorkflowResult("sage", {source.name: source}),
        Dataset(()),
        Database(tmp_path / "unused.fasta", "fasta"),
        output_dir=tmp_path / "evaluation",
    )
    assert result.metrics["expected_recovery_at_threshold"] == 1
