"""Load separate component definitions and construct selected experiments."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from interop_trace.components import Registry
from interop_trace.databases import DatabaseProvider
from interop_trace.datasets import DatasetProvider
from interop_trace.evaluation import Benchmark
from interop_trace.registries import (
    benchmarks,
    databases,
    datasets,
    workflows,
)
from interop_trace.workflows import Workflow


@dataclass(frozen=True)
class Experiment:
    """One named combination of configured components, not yet set up."""

    id: str
    dataset: DatasetProvider
    database: DatabaseProvider
    workflow: Workflow
    benchmark: Benchmark | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", self.id)
            or self.id == "configuration.json"
        ):
            raise ValueError(
                "Experiment id must be a simple directory name "
                "starting with a letter or digit, "
                "excluding configuration.json."
            )


@dataclass(frozen=True)
class RunConfiguration:
    """Constructed experiments and a snapshot of all referenced YAML contents."""

    experiments: tuple[Experiment, ...]
    snapshot: dict[str, Any]

    def __post_init__(self) -> None:
        names = [experiment.id for experiment in self.experiments]
        if not names or len(set(names)) != len(names):
            raise ValueError("Experiment ids must be unique and the run nonempty.")


def load_configuration(path: Path) -> RunConfiguration:
    """Validate references and construct every experiment before any setup.

    Each layer references one component file. Paths resolve relative to the file
    containing them. Constructors accept implementation-specific parameters.
    The loader never downloads resources or starts workflow processes.
    """
    path = path.resolve()
    document, text = _read_yaml(path)
    _keys(document, {"components", "experiments"}, str(path))
    definitions, contents = _read_component_files(document["components"], path.parent)
    choices = document["experiments"]
    if not isinstance(choices, list) or not choices:
        raise ValueError("experiments must be a nonempty list.")
    experiments = tuple(_build_experiment(choice, definitions) for choice in choices)
    return RunConfiguration(
        experiments,
        {
            "source": str(path),
            "files": {str(path): text, **contents},
            "experiments": choices,
        },
    )


def _read_component_files(
    sources: object, directory: Path
) -> tuple[dict[str, tuple[Path, dict[str, Any]]], dict[str, str]]:
    sources = _mapping(sources, "components")
    _keys(
        sources,
        {"datasets", "databases", "workflows"},
        "components",
        optional={"benchmarks"},
    )
    definitions, contents = {}, {}
    for layer, relative in sources.items():
        if not isinstance(relative, str):
            raise ValueError(f"components.{layer} must reference a YAML file.")
        path = (directory / relative).resolve()
        document, text = _read_yaml(path)
        definitions[layer] = (path, document)
        contents[str(path)] = text
    return definitions, contents


def _build_experiment(
    choice: object, definitions: dict[str, tuple[Path, dict[str, Any]]]
) -> Experiment:
    choice = _mapping(choice, "experiment")
    _keys(
        choice,
        {"id", "dataset", "database", "workflow"},
        "experiment",
        optional={"benchmark"},
    )
    benchmark = None
    if choice.get("benchmark") is not None:
        if "benchmarks" not in definitions:
            raise ValueError(
                "An experiment selects a benchmark but no benchmarks file is provided."
            )
        benchmark = _build_component(
            benchmarks, choice["benchmark"], definitions["benchmarks"]
        )
    return Experiment(
        id=choice["id"],
        dataset=_build_component(datasets, choice["dataset"], definitions["datasets"]),
        database=_build_component(
            databases, choice["database"], definitions["databases"]
        ),
        workflow=_build_component(
            workflows, choice["workflow"], definitions["workflows"]
        ),
        benchmark=benchmark,
    )


def _build_component[T](
    registry: Registry[T], reference: object, definitions: tuple[Path, dict[str, Any]]
) -> T:
    source, available = definitions
    if not isinstance(reference, str) or reference not in available:
        raise ValueError(f"Unknown component definition {reference!r} in {source}.")
    definition = _mapping(available[reference], f"{source}:{reference}")
    _keys(definition, {"type"}, reference, optional={"parameters"})
    implementation = definition["type"]
    if not isinstance(implementation, str):
        raise ValueError(f"{reference}.type must be a registered name.")
    parameters = _mapping(definition.get("parameters", {}), "parameters")
    return registry.create(implementation, parameters, base_dir=source.parent)


def _mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be a mapping with string keys.")
    return value


def _keys(
    value: dict[str, Any],
    required: set[str],
    context: str,
    *,
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    missing, unknown = required - value.keys(), value.keys() - required - optional
    if missing or unknown:
        raise ValueError(
            f"Invalid {context}: missing {sorted(missing)}, unknown {sorted(unknown)}."
        )


def _unique_mapping(loader: Any, node: Any) -> dict[str, Any]:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise ValueError(f"YAML keys must be unique strings; found {key!r}.")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


class _UniqueSafeLoader(yaml.SafeLoader):
    """Safe YAML construction that also rejects silently overwritten settings."""


def _read_yaml(path: Path) -> tuple[dict[str, Any], str]:
    _UniqueSafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
    )
    text = path.read_text(encoding="utf-8")
    try:
        value = yaml.load(text, Loader=_UniqueSafeLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error
    return _mapping(value, str(path)), text
