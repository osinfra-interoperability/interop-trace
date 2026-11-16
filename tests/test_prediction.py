"""Exercise the declared-interface baseline without tools, outcomes or network."""

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from interop_trace.edam import Edam
from interop_trace.experiments.records import experiment_rows, save_table
from interop_trace.prediction import predict_interoperability, predict_run


def port(data: str, format_: str) -> dict[str, Any]:
    return {
        "data": {"uri": f"http://edamontology.org/{data}"},
        "format": [{"uri": f"http://edamontology.org/{format_}"}],
    }


SPECTRUM = port("data_0943", "format_3244")
PROTEIN = port("data_2976", "format_1929")


@pytest.fixture
def ontology(edam_path: Path) -> Edam:
    return Edam.from_responses(json.loads(edam_path.read_text()))


@pytest.mark.parametrize(
    "systems,types,expected,coverage,applicable",
    [
        (["Mac", "Linux"], [], "support", 5 / 7, True),
        (["Windows"], [], "conflict", 5 / 7, True),
        ([], [], "support", 4 / 7, True),
        (["Other"], [], "support", 4 / 7, True),
        (["Windows"], ["Web API"], "support", 4 / 6, False),
        (["Windows"], ["Web API", "Command-line tool"], "support", 4 / 7, True),
    ],
)
def test_platform_and_coverage(
    ontology, systems, types, expected, coverage, applicable
) -> None:
    entries = {
        "dataset": {
            "function": [{"output": [port("data_9999", "format_9999"), SPECTRUM]}]
        },
        "database": {"function": [{"output": [PROTEIN]}]},
        "workflow": {
            "function": [
                {"input": []},
                {"input": [PROTEIN, SPECTRUM, port("data_9999", "format_9999")]},
            ],
            "operatingSystem": systems,
            "toolType": types,
        },
    }
    result = predict_interoperability(entries, {"operating_system": "Darwin"}, ontology)
    assert result["conclusion"] == expected
    assert result["evidence_coverage"] == coverage
    assert result["failure_probability"] is None
    assert result["checks"]["workflow_platform"]["applicable"] is applicable
    assert result["aspects"]["semantic"] == {
        "conclusion": "support",
        "evidence_coverage": 1,
    }
    assert result["checks"]["dataset_data"]["pair"] == {
        "output": "dataset#/function/0/output/1",
        "input": "workflow#/function/1/input/1",
    }


def test_local_producer_os_conflict_and_remote_exclusion(ontology) -> None:
    result = predict_interoperability(
        {
            "dataset": {
                "toolType": ["Command-line tool"],
                "operatingSystem": ["Linux"],
            },
            "database": {
                "toolType": ["Database portal"],
                "operatingSystem": ["Windows"],
            },
            "workflow": {"operatingSystem": ["Mac"]},
        },
        {"operating_system": "Darwin"},
        ontology,
    )
    assert result["checks"]["dataset_platform"]["conclusion"] == "conflict"
    assert result["checks"]["database_platform"]["applicable"] is False
    assert result["aspects"]["technical"] == {
        "conclusion": "conflict",
        "evidence_coverage": 0.5,
    }


@pytest.mark.parametrize(
    "dataset,expected,coverage",
    [
        ({"function": [{"output": [PROTEIN]}]}, "support", 4 / 7),
        (
            {"function": [{"output": [port("data_0943", "format_1062")]}]},
            "support",
            3 / 7,
        ),
        (
            {"function": [{"output": [{"data": SPECTRUM["data"], "format": []}]}]},
            "support",
            3 / 7,
        ),
        (
            {"function": [{"output": [SPECTRUM]}, {"output": [SPECTRUM]}]},
            "support",
            4 / 7,
        ),
        (
            {"toolType": ["Database portal"], "function": [{"output": [SPECTRUM]}]},
            "support",
            2 / 6,
        ),
        ({}, "support", 2 / 7),
    ],
)
def test_connections_preserve_partial_evidence(
    ontology, dataset, expected, coverage
) -> None:
    result = predict_interoperability(
        {
            "dataset": dataset,
            "database": {"function": [{"output": [PROTEIN]}]},
            "workflow": {
                "function": [{"input": [SPECTRUM, port("data_2044", "format_2330")]}]
            },
        },
        {},
        ontology,
    )
    assert result["conclusion"] == expected
    assert result["evidence_coverage"] == coverage
    assert result["checks"]["database_data"]["match"]["relation"] == "subclass"
    assert result["checks"]["database_format"]["match"]["relation"] == "subclass"


def test_data_and_format_support_must_come_from_the_same_pair(ontology) -> None:
    result = predict_interoperability(
        {
            "dataset": {"function": [{"output": [SPECTRUM]}]},
            "workflow": {
                "function": [
                    {
                        "input": [
                            port("data_0943", "format_1929"),
                            port("data_2976", "format_3244"),
                        ]
                    }
                ]
            },
        },
        {},
        ontology,
    )
    assert result["checks"]["dataset_data"]["conclusion"] == "support"
    assert result["checks"]["dataset_format"]["conclusion"] == "unknown"
    assert (
        result["checks"]["dataset_data"]["pair"]
        == result["checks"]["dataset_format"]["pair"]
    )
    assert result["evidence_coverage"] == 1 / 7


def test_run_predictions_preserve_sources_and_do_not_read_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "configuration.json").write_text(
        json.dumps({"experiments": [{"id": "first"}, {"id": "second"}]})
    )
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "term.json").write_text(
        '{"iri":"http://edamontology.org/data_0943","isObsolete":false,"directAncestor":[]}'
    )
    (metadata / "entry.json").write_text('{"operatingSystem":["Linux"]}')
    (metadata / "index.json").write_text(
        json.dumps(
            {
                "ontology": {
                    "status": "collected",
                    "requests": [
                        {
                            "status": "collected",
                            "term": "http://edamontology.org/data_0943",
                            "response": "term.json",
                        }
                    ],
                },
                "components": [
                    {
                        "experiment": "first",
                        "role": "workflow",
                        "status": "collected",
                        "directory": ".",
                    },
                    {"experiment": "second", "role": "workflow", "status": "not_found"},
                ],
            }
        )
    )
    for name in ("first", "second"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(
        "interop_trace.prediction.capture_environment",
        lambda: {"operating_system": "Linux"},
    )
    read_text = Path.read_text

    def read_inputs_only(path, *args, **kwargs):
        assert path.name not in {
            "experiment.json",
            "classification.json",
            "metrics.json",
        }
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_inputs_only)
    outputs = predict_run(tmp_path)
    first, second = [json.loads(output.read_text()) for output in outputs]
    assert first["conclusion"] == "support"
    assert first["evidence_coverage"] == 1 / 7
    assert second["evidence_coverage"] == 0
    assert first["metadata"]["workflow"] == {
        "index": "../metadata/index.json",
        "rows": [0],
        "entry": "../metadata/entry.json",
        "status": "collected",
    }
    assert second["metadata"]["workflow"]["status"] == "not_found"
    assert first["environment"] == "../prediction_environment.json"
    assert first["ontology"] == {
        "index": "../metadata/index.json#/ontology",
        "unreadable": [],
    }
    assert json.loads((tmp_path / "prediction_environment.json").read_text()) == {
        "operating_system": "Linux"
    }
    before = outputs[0].read_bytes()
    with pytest.raises(FileExistsError):
        predict_run(tmp_path)
    assert outputs[0].read_bytes() == before
    (tmp_path / "execution.json").touch()
    with pytest.raises(ValueError, match="before execution"):
        predict_run(tmp_path)
    monkeypatch.setattr(Path, "read_text", read_text)
    save_table(tmp_path)
    with (tmp_path / "experiments.csv").open() as stream:
        saved = list(csv.DictReader(stream))
    for row in (saved[0], experiment_rows(tmp_path)[0]):
        assert row["technical_prediction"] == "support"
        assert row["technical_coverage"] == str(1 / 5)
        assert row["semantic_prediction"] == "unknown"
        assert row["semantic_coverage"] == "0.0"
