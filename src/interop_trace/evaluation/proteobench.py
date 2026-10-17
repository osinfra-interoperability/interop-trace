"""Local ProteoBench evaluation of Sage LFQ results for the Q Exactive design."""

import json
import math
import shutil
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from interop_trace.databases import Database
from interop_trace.datasets import Dataset
from interop_trace.evaluation.base import EvaluationResult
from interop_trace.workflows import WorkflowResult

_MODULE = "quant_lfq_DDA_ion_QExactive"
_SETTINGS = ("module_settings.toml", "parse_settings_sage.toml")


@dataclass(frozen=True)
class ProteoBenchDDA:
    """ProteoBench's six-run Q Exactive DDA ion benchmark, using Sage outputs.

    ``min_observations`` is the minimum number of the six runs in which an ion
    must be quantified. The reference mixture and run names come from ProteoBench.
    The search database is recorded as provenance, rather than used as ground truth.
    """

    min_observations: int = 3

    def evaluate(
        self,
        result: WorkflowResult,
        dataset: Dataset,
        database: Database,
        *,
        output_dir: Path,
    ) -> EvaluationResult:
        """Score locally and preserve the metrics, per-ion table and settings.

        Require Sage's ``lfq.tsv`` and ``results.json`` and the six reference run
        names. Reports use a new directory. Undefined metrics are listed in the
        JSON report and omitted from the numeric result. No data are submitted.
        """
        if result.format != "sage":
            raise ValueError("ProteoBenchDDA currently accepts Sage results only.")
        if not 1 <= self.min_observations <= 6:
            raise ValueError("min_observations must be between 1 and 6.")
        try:
            lfq = result.files["lfq.tsv"]
            parameters = json.loads(result.files["results.json"].read_bytes())
        except KeyError as error:
            raise ValueError(
                "ProteoBenchDDA requires Sage lfq.tsv and results.json."
            ) from error
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=False)
        parser, settings_dir = _load_parser()
        _validate_runs(dataset, set(parser.condition_mapper))
        table, metrics, undefined = _score(lfq, dataset, parser, self.min_observations)
        table.to_csv(output_dir / "ions.tsv", sep="\t", index=False)
        for name in _SETTINGS:
            shutil.copyfile(settings_dir / name, output_dir / name)
        record = {
            "benchmark": _MODULE,
            "proteobench_version": version("proteobench"),
            "min_observations": self.min_observations,
            "dataset": asdict(dataset),
            "database": asdict(database),
            "workflow": asdict(result),
            "sage_parameters": parameters,
            "metrics": metrics,
            "undefined_metrics": undefined,
        }
        (output_dir / "proteobench.json").write_text(
            json.dumps(record, default=str, allow_nan=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return EvaluationResult(
            metrics=metrics,
            reports=tuple(
                output_dir / name
                for name in ("proteobench.json", "ions.tsv", *_SETTINGS)
            ),
        )


def _load_parser() -> tuple[Any, Path]:
    try:
        from proteobench.io.parsing.parse_settings import ParseSettingsBuilder
        from proteobench.modules.constants import MODULE_SETTINGS_DIRS
    except ModuleNotFoundError as error:
        if error.name == "proteobench":
            raise RuntimeError(
                "Install ProteoBench with: poetry install --extras proteobench"
            ) from error
        raise
    directory = Path(MODULE_SETTINGS_DIRS[_MODULE])
    parser = ParseSettingsBuilder(str(directory), _MODULE).build_parser("Sage")
    return parser, directory


def _validate_runs(dataset: Dataset, expected: set[str]) -> None:
    names = [Path(path.name.removesuffix(".gz")).stem for path in dataset.files]
    if len(names) != len(expected) or set(names) != expected:
        raise ValueError(
            "ProteoBenchDDA requires its six distinct published Q Exactive runs. "
            f"Missing: {sorted(expected - set(names))}; "
            f"unexpected: {sorted(set(names) - expected)}."
        )


def _score(
    lfq: Path, dataset: Dataset, parser: Any, threshold: int
) -> tuple[Any, dict[str, int | float], list[str]]:
    from proteobench.datapoint.quant_datapoint import QuantDatapointHYE
    from proteobench.io.parsing.parse_ion import load_input_file
    from proteobench.score.quantscoresHYE import QuantScoresHYE

    data = load_input_file(str(lfq), "Sage")
    if not data["charge"].gt(0).all():
        raise ValueError(
            "ProteoBenchDDA requires separate precursor charge states. "
            "Set quant.lfq_settings.combine_charge_states=false in Sage."
        )
    data = data.rename(
        columns={str(path.resolve()): path.name for path in dataset.files}
    )
    standard, mapping = parser.convert_to_standard_format(data)
    table = QuantScoresHYE(
        "precursor ion", parser.species_expected_ratio(), parser.species_dict()
    ).generate_intermediate(standard, mapping)
    raw = QuantDatapointHYE.get_metrics(table, threshold)[threshold]
    if not raw["nr_feature"]:
        raise ValueError(
            "No species-specific precursor ions meet the observation threshold."
        )
    metrics: dict[str, int | float] = {
        name: float(value) for name, value in raw.items() if math.isfinite(value)
    }
    metrics["nr_feature"] = int(raw["nr_feature"])
    return table, metrics, sorted(set(raw) - set(metrics))
