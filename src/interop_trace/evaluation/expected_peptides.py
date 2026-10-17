"""Check a small, explicitly declared peptide reference against Sage output."""

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.evaluation.base import EvaluationResult
from interop_trace.evaluation.registry import registry
from interop_trace.workflows import WorkflowResult


@registry.register(
    "expected_peptides",
    summary="Expected-peptide recovery from Sage target matches",
    documentation="components.md#expected-peptides",
)
@dataclass(frozen=True)
class ExpectedPeptides:
    """Count exact peptide strings among rank-one target PSMs.

    Expectations must come from an independent reference, not the search database.
    Recovery is diagnostic: it does not estimate precision, FDR or quantification
    accuracy. Modified sequences must use Sage's exact output notation.
    """

    peptides: tuple[str, ...]
    max_q_value: float = 0.01

    def __post_init__(self) -> None:
        if (
            not self.peptides
            or isinstance(self.peptides, str)
            or any(not isinstance(p, str) or not p.strip() for p in self.peptides)
            or len(set(self.peptides)) != len(self.peptides)
        ):
            raise ValueError("peptides must contain distinct, nonempty strings.")
        if (
            isinstance(self.max_q_value, bool)
            or not isinstance(self.max_q_value, (int, float))
            or not 0 <= self.max_q_value <= 1
        ):
            raise ValueError("max_q_value must be a number between 0 and 1.")

    def evaluate(
        self,
        result: WorkflowResult,
        dataset: Dataset,
        database: Database,
        *,
        output_dir: Path,
    ) -> EvaluationResult:
        """Report recovery before and after the spectrum q-value threshold."""
        if result.format != "sage":
            raise ValueError("ExpectedPeptides currently reads Sage TSV output only.")
        source = result.files["results.sage.tsv"]
        observed, accepted = _read_peptides(source, self.max_q_value)
        expected = set(self.peptides)
        matched, passing = expected & observed, expected & accepted
        metrics = {
            "expected_peptides": len(expected),
            "matched_expected_peptides": len(matched),
            "matched_expected_peptides_at_threshold": len(passing),
            "expected_recovery_at_threshold": len(passing) / len(expected),
        }
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        report = output_dir / "expected_peptides.json"
        report.write_text(
            json.dumps(
                {
                    "source": str(source),
                    "max_q_value": self.max_q_value,
                    "expected": sorted(expected),
                    "matched": sorted(matched),
                    "matched_at_threshold": sorted(passing),
                    "missing_at_threshold": sorted(expected - passing),
                    "metrics": metrics,
                },
                indent=2,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return EvaluationResult(metrics, (report,))


def _read_peptides(path: Path, threshold: float) -> tuple[set[str], set[str]]:
    observed, accepted = set(), set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {"peptide", "rank", "label", "spectrum_q"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Sage table must contain {sorted(required)}.")
        for row in reader:
            if int(row["rank"]) != 1 or int(row["label"]) != 1:
                continue
            peptide, q_value = row["peptide"], float(row["spectrum_q"])
            if not peptide or not math.isfinite(q_value) or not 0 <= q_value <= 1:
                raise ValueError("Invalid peptide or spectrum_q in Sage target row.")
            observed.add(peptide)
            if q_value <= threshold:
                accepted.add(peptide)
    return observed, accepted
