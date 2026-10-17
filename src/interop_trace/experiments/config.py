"""Load separate component definitions and construct selected experiments."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from interop_trace.catalogue import REGISTRIES
from interop_trace.databases import DatabaseProvider
from interop_trace.datasets import DatasetProvider
from interop_trace.evaluation import Benchmark
from interop_trace.workflows import Workflow

_ROLES = {
    "dataset": "datasets",
    "database": "databases",
    "workflow": "workflows",
    "benchmark": "benchmarks",
}


@dataclass(frozen=True)
class Experiment:
    """One named combination of configured components, not yet set up."""

    id: str
    dataset: DatasetProvider
    database: DatabaseProvider
    workflow: Workflow
    benchmark: Benchmark
    settings: dict[str, Any]


@dataclass(frozen=True)
class RunConfiguration:
    """Constructed experiments and a snapshot of all referenced YAML contents."""

    experiments: tuple[Experiment, ...]
    snapshot: dict[str, Any]


def load_configuration(path: Path) -> RunConfiguration:
    """Validate references and construct every experiment before any setup.

    Each layer references one component file. Paths resolve relative to the file
    containing them. Constructors accept implementation-specific parameters.
    The loader never downloads resources or starts workflow processes.
    """
    path = path.resolve()
    document = _read_yaml(path)
    _keys(document, {"components", "experiments"}, str(path))
    sources = _mapping(document["components"], "components")
    _keys(sources, set(REGISTRIES), "components")
    definitions = {}
    contents = {str(path): path.read_text(encoding="utf-8")}
    for layer, relative in sources.items():
        if not isinstance(relative, str):
            raise ValueError(f"components.{layer} must reference a YAML file.")
        source = (path.parent / relative).resolve()
        definitions[layer] = (source, _read_yaml(source))
        contents[str(source)] = source.read_text(encoding="utf-8")
    choices = document["experiments"]
    if not isinstance(choices, list) or not choices:
        raise ValueError("experiments must be a nonempty list.")
    experiments = tuple(_build_experiment(choice, definitions) for choice in choices)
    names = [experiment.id for experiment in experiments]
    if len(set(names)) != len(names):
        raise ValueError("Experiment ids must be unique within a run.")
    return RunConfiguration(experiments, {"source": str(path), "files": contents})


def _build_experiment(
    choice: object, definitions: dict[str, tuple[Path, dict[str, Any]]]
) -> Experiment:
    choice = _mapping(choice, "experiment")
    _keys(choice, {"id", *_ROLES}, "experiment")
    name = choice["id"]
    if not isinstance(name, str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9._-]*", name
    ):
        raise ValueError(
            "Experiment id must be a simple directory name "
            "starting with a letter or digit."
        )
    components, settings = {}, {}
    for role, layer in _ROLES.items():
        source, available = definitions[layer]
        reference = choice[role]
        if not isinstance(reference, str) or reference not in available:
            raise ValueError(f"Unknown {role} definition {reference!r} in {source}.")
        definition = _mapping(available[reference], f"{layer}.{reference}")
        _keys(definition, {"type"}, f"{layer}.{reference}", optional={"parameters"})
        implementation = definition["type"]
        if not isinstance(implementation, str):
            raise ValueError(f"{layer}.{reference}.type must be a registered name.")
        parameters = _mapping(definition.get("parameters", {}), "parameters")
        components[role] = REGISTRIES[layer].create(
            implementation, parameters, base_dir=source.parent
        )
        settings[role] = {"reference": reference, "source": str(source), **definition}
    return Experiment(name, **components, settings=settings)


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


def _read_yaml(path: Path) -> dict[str, Any]:
    _UniqueSafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
    )
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueSafeLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error
    return _mapping(value, str(path))
