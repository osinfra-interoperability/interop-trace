"""Load separate YAML definitions without downloading or executing components."""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

from interop_trace.databases import UniProtProvider
from interop_trace.experiments import load_configuration
from interop_trace.workflows import SageWorkflow


@pytest.fixture
def configuration(tmp_path: Path) -> Path:
    directory = tmp_path / "components"
    directory.mkdir()
    definitions = {
        "datasets": {
            "type": "pride",
            "parameters": {"project": "PXD1", "files": ["a.mzML"]},
        },
        "databases": {"type": "uniprot", "parameters": {"query": "accession:P69905"}},
        "workflows": {
            "type": "sage",
            "parameters": {"configuration": "../settings.json", "threads": 3},
        },
        "benchmarks": {
            "type": "proteobench_dda",
            "parameters": {"min_observations": 3},
        },
    }
    for layer, definition in definitions.items():
        (directory / f"{layer}.yaml").write_text(
            yaml.safe_dump({"selected": definition})
        )
    document = {
        "components": {layer: f"components/{layer}.yaml" for layer in definitions},
        "experiments": [
            {
                "id": "first",
                "dataset": "selected",
                "database": "selected",
                "workflow": "selected",
                "benchmark": "selected",
            }
        ],
    }
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump(document))
    return path


def test_load_resolves_paths_and_keeps_definition_contents(
    configuration: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    http_transport: Mock,
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    loaded = load_configuration(configuration)
    experiment = loaded.experiments[0]
    assert experiment.id == "first"
    assert isinstance(experiment.workflow, SageWorkflow)
    assert experiment.workflow.configuration == configuration.parent / "settings.json"
    assert experiment.workflow.threads == 3
    assert isinstance(experiment.database, UniProtProvider)
    assert experiment.database.query == "accession:P69905"
    assert len(loaded.snapshot["files"]) == 5
    assert loaded.snapshot["files"][str(configuration)] == configuration.read_text()
    assert loaded.snapshot["experiments"][0]["database"] == "selected"
    http_transport.assert_not_called()


def test_reused_definitions_construct_independent_instances(
    configuration: Path,
) -> None:
    document = yaml.safe_load(configuration.read_text())
    document["experiments"].append({**document["experiments"][0], "id": "second"})
    configuration.write_text(yaml.safe_dump(document))
    first, second = load_configuration(configuration).experiments
    assert first.dataset is not second.dataset
    assert first.workflow is not second.workflow
    assert first.database == second.database


@pytest.mark.parametrize(
    "experiment_id",
    ["../outside", "/absolute", ".", "", False, "configuration.json"],
)
def test_ids_cannot_escape_run_directory(
    configuration: Path, experiment_id: object
) -> None:
    document = yaml.safe_load(configuration.read_text())
    document["experiments"][0]["id"] = experiment_id
    configuration.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="simple directory name"):
        load_configuration(configuration)


def test_duplicate_ids_are_rejected(configuration: Path) -> None:
    document = yaml.safe_load(configuration.read_text())
    document["experiments"] *= 2
    configuration.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="unique"):
        load_configuration(configuration)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"type": "unknown"}, "Unknown component"),
        ({"parameters": {"configuration": "x.json", "threds": 3}}, "Invalid settings"),
        (
            {"parameters": {"configuration": "x.json", "threads": "three"}},
            "positive integer",
        ),
        ({"parameters": {"configuration": 42}}, "file path"),
        ({"unexpected": True}, "unknown"),
    ],
)
def test_invalid_component_settings_fail_before_setup(
    configuration: Path, change: dict[str, object], message: str, http_transport: Mock
) -> None:
    path = configuration.parent / "components/workflows.yaml"
    document = yaml.safe_load(path.read_text())
    document["selected"].update(change)
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match=message):
        load_configuration(configuration)
    http_transport.assert_not_called()


def test_unknown_reference_in_later_experiment_fails_before_setup(
    configuration: Path, http_transport: Mock
) -> None:
    document = yaml.safe_load(configuration.read_text())
    document["experiments"].append(
        {**document["experiments"][0], "id": "second", "database": "missing"}
    )
    configuration.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="Unknown component definition"):
        load_configuration(configuration)
    http_transport.assert_not_called()


@pytest.mark.parametrize(
    "text", ["duplicate: 1\nduplicate: 2\n", "!!python/object:builtins.object {}"]
)
def test_ambiguous_or_executable_yaml_is_rejected(
    configuration: Path, text: str
) -> None:
    configuration.write_text(text)
    with pytest.raises(ValueError):
        load_configuration(configuration)


def test_snapshot_preserves_parsed_text_when_source_changes(
    configuration: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_read = Path.read_text
    original_text = configuration.read_text()

    def read_and_edit(path: Path, *args: Any, **kwargs: Any) -> str:
        text = original_read(path, *args, **kwargs)
        if path == configuration:
            path.write_text(text.replace("first", "edited"))
        return text

    monkeypatch.setattr(Path, "read_text", read_and_edit)
    loaded = load_configuration(configuration)
    assert loaded.experiments[0].id == "first"
    assert loaded.snapshot["files"][str(configuration)] == original_text
