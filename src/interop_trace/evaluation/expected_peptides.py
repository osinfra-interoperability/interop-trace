"""Check an explicit peptide reference against native search-engine output."""

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.evaluation.base import EvaluationResult
from interop_trace.evaluation.registry import registry
from interop_trace.workflows import WorkflowResult


@registry.register(
    "expected_peptides",
    summary="Expected-peptide recovery from target matches",
    documentation="components.md#expected-peptides",
)
@dataclass(frozen=True)
class ExpectedPeptides:
    """Count exact peptide strings among rank-one target PSMs.

    Expectations must come from an independent reference, not the search database.
    Recovery is diagnostic: it does not estimate precision, FDR or quantification
    accuracy. Exact Sage notation remains the default. Sequence-only matching
    ignores modifications and also supports Comet and MS Amanda native tables.
    """

    peptides: tuple[str, ...]
    max_q_value: float | None = 0.01
    sequence_only: bool = False

    def __post_init__(self) -> None:
        if (
            not self.peptides
            or isinstance(self.peptides, str)
            or any(not isinstance(p, str) or not p.strip() for p in self.peptides)
            or len(set(self.peptides)) != len(self.peptides)
        ):
            raise ValueError("peptides must contain distinct, nonempty strings.")
        if self.max_q_value is not None and (
            isinstance(self.max_q_value, bool)
            or not isinstance(self.max_q_value, (int, float))
            or not 0 <= self.max_q_value <= 1
        ):
            raise ValueError("max_q_value must be a number between 0 and 1.")
        if type(self.sequence_only) is not bool:
            raise ValueError("sequence_only must be a boolean.")
        if self.sequence_only and any(
            not re.fullmatch("[A-Z]+", p) for p in self.peptides
        ):
            raise ValueError("sequence_only expects unmodified uppercase peptides.")

    def evaluate(
        self,
        result: WorkflowResult,
        dataset: Dataset,
        database: Database,
        *,
        output_dir: Path,
    ) -> EvaluationResult:
        """Report recovery, applying a confidence threshold only when requested."""
        sources, observed, accepted = self._observed(result)
        if self.sequence_only and result.format == "sage":
            observed = {_sage_sequence(p) for p in observed}
            accepted = (
                {_sage_sequence(p) for p in accepted} if accepted is not None else None
            )
        expected = set(self.peptides)
        matched = expected & observed
        metrics = {
            "expected_peptides": len(expected),
            "matched_expected_peptides": len(matched),
            "expected_recovery": len(matched) / len(expected),
        }
        record: dict[str, object] = {
            "source": str(sources[0]) if len(sources) == 1 else None,
            "sources": [str(p) for p in sources],
            "max_q_value": self.max_q_value,
            "sequence_only": self.sequence_only,
            "confidence_filter": "spectrum_q" if accepted is not None else "none",
            "expected": sorted(expected),
            "matched": sorted(matched),
            "missing": sorted(expected - matched),
            "metrics": metrics,
        }
        if accepted is not None:
            passing = expected & accepted
            metrics.update(
                matched_expected_peptides_at_threshold=len(passing),
                expected_recovery_at_threshold=len(passing) / len(expected),
            )
            record.update(
                matched_at_threshold=sorted(passing),
                missing_at_threshold=sorted(expected - passing),
            )
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        report = output_dir / "expected_peptides.json"
        report.write_text(
            json.dumps(record, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return EvaluationResult(metrics, (report,))

    def _observed(
        self, result: WorkflowResult
    ) -> tuple[list[Path], set[str], set[str] | None]:
        if result.format == "sage":
            source = result.files["results.sage.tsv"]
            observed, accepted = _read_peptides(source, self.max_q_value)
            return [source], observed, accepted
        if result.format not in {"comet", "msamanda"}:
            raise ValueError(
                "ExpectedPeptides accepts Sage, Comet or MS Amanda results."
            )
        if self.max_q_value is not None or not self.sequence_only:
            raise ValueError(
                "Comet/MS Amanda recovery requires max_q_value=null "
                "and sequence_only=true; "
                "native scores are not spectrum q-values."
            )
        suffix = ".comet.txt" if result.format == "comet" else ".msamanda.csv"
        sources = sorted(p for name, p in result.files.items() if name.endswith(suffix))
        if not sources:
            raise ValueError(f"No native {suffix} result tables.")
        observed = set().union(*(_read_native(p, result.format) for p in sources))
        return sources, observed, None


def _sage_sequence(peptide: str) -> str:
    return re.sub(r"\[[^]]*\]|-", "", peptide)


def _read_peptides(
    path: Path, threshold: float | None
) -> tuple[set[str], set[str] | None]:
    observed: set[str] = set()
    accepted: set[str] | None = set() if threshold is not None else None
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
            if threshold is not None and accepted is not None and q_value <= threshold:
                accepted.add(peptide)
    return observed, accepted


def _read_native(path: Path, format: str) -> set[str]:
    peptide, rank, proteins, separator, decoy_prefix = {
        "comet": ("plain_peptide", "num", "protein", ",", "DECOY_"),
        "msamanda": ("Sequence", "Rank", "Protein Accessions", ";", "REV_"),
    }[format]
    observed = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if not stream.readline().startswith(("#", "CometVersion")):
            stream.seek(0)
        reader = csv.DictReader(stream, delimiter="\t")
        required = {peptide, rank, proteins}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{format} table must contain {sorted(required)}.")
        for row in reader:
            if int(row[rank]) != 1:
                continue
            accessions = [p.strip() for p in row[proteins].split(separator)]
            if not any(p and not p.startswith(decoy_prefix) for p in accessions):
                continue
            sequence = row[peptide].upper()
            if not re.fullmatch("[A-Z]+", sequence):
                raise ValueError(f"Invalid peptide sequence in {format} target row.")
            observed.add(sequence)
    return observed
