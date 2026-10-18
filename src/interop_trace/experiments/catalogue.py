"""Discover root-level experiment files and select a run by experiment ID."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from interop_trace.experiments.config import (
    Experiment,
    RunConfiguration,
    load_configuration,
)


def load_experiments(
    directory: Path, ids: Sequence[str] | None = None
) -> RunConfiguration:
    """Validate the catalogue without setup; select IDs in the requested order.

    Only immediate YAML files are discovered. ``None`` selects every experiment;
    an explicit selection must be nonempty. Source and component YAML contents
    are retained for the selected experiments, with globally unique IDs.
    """
    directory = directory.resolve()
    configurations = {}
    available: dict[str, tuple[Experiment, dict[str, Any]]] = {}
    paths = sorted({*directory.glob("*.yaml"), *directory.glob("*.yml")})
    for path in paths:
        configuration = load_configuration(path)
        configurations[str(path)] = configuration
        for experiment, choice in zip(
            configuration.experiments,
            configuration.snapshot["experiments"],
            strict=True,
        ):
            if experiment.id in available:
                previous = available[experiment.id][1]["source"]
                raise ValueError(
                    f"Duplicate experiment id {experiment.id!r} "
                    f"in {previous} and {path}."
                )
            available[experiment.id] = (experiment, {**choice, "source": str(path)})
    if not available:
        raise ValueError(f"No experiments found in {directory}/*.yaml or *.yml.")
    selected = list(available) if ids is None else list(ids)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Select one or more unique experiment IDs.")
    unknown = set(selected) - available.keys()
    if unknown:
        raise ValueError(f"Unknown experiment IDs: {', '.join(sorted(unknown))}.")
    choices = [available[name][1] for name in selected]
    sources = list(dict.fromkeys(choice["source"] for choice in choices))
    return RunConfiguration(
        tuple(available[name][0] for name in selected),
        {
            "sources": sources,
            "files": {
                path: text
                for source in sources
                for path, text in configurations[source].snapshot["files"].items()
            },
            "experiments": choices,
        },
    )
