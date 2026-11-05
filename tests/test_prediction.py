"""Exercise the declared-interface baseline without tools, outcomes or network."""

import json
from pathlib import Path
from typing import Any

import pytest

from interop_trace.prediction import predict_interoperability, predict_run


def port(data: str, format_: str) -> dict[str, Any]:
    return {
        "data": {"uri": f"http://edamontology.org/{data}"},
        "format": [{"uri": f"http://edamontology.org/{format_}"}],
    }


SPECTRUM = port("data_0943", "format_3244")
PROTEIN = port("data_2976", "format_1929")


@pytest.mark.parametrize(
    "systems,types,expected,coverage,applicable",
    [
        (["Mac", "Linux"], [], "support", 1, True),
        (["Windows"], [], "conflict", 1, True),
        ([], [], "unknown", 0.5, True),
        (["Other"], [], "unknown", 0.5, True),
        (["Windows"], ["Web API"], "support", 1, False),
        (["Windows"], ["Web API", "Command-line tool"], "unknown", 0.5, True),
    ],
)
def test_platform_and_coverage(systems, types, expected, coverage, applicable) -> None:
    entries = {
        "dataset": {"function": [{"output": [SPECTRUM]}]},
        "database": {"function": [{"output": [PROTEIN]}]},
        "workflow": {
            "function": [{"input": [PROTEIN, SPECTRUM]}],
            "operatingSystem": systems,
            "toolType": types,
        },
    }
    result = predict_interoperability(entries, {"operating_system": "Darwin"})
    assert result["conclusion"] == expected
    assert result["evidence_coverage"] == coverage
    assert result["failure_probability"] is None
    assert result["checks"]["workflow_platform"]["applicable"] is applicable


@pytest.mark.parametrize(
    "dataset,expected,coverage",
    [
        ({"function": [{"output": [PROTEIN]}]}, "conflict", 0.5),
        (
            {"function": [{"output": [port("data_0943", "format_1062")]}]},
            "conflict",
            0.5,
        ),
        (
            {"function": [{"output": [{"data": SPECTRUM["data"], "format": []}]}]},
            "unknown",
            0,
        ),
        ({"function": [{"output": [SPECTRUM]}, {"output": [SPECTRUM]}]}, "unknown", 0),
        (
            {"toolType": ["Database portal"], "function": [{"output": [SPECTRUM]}]},
            "unknown",
            0,
        ),
        ({}, "unknown", 0),
    ],
)
def test_interfaces_require_distinct_inputs_and_unambiguous_exports(
    dataset, expected, coverage
) -> None:
    result = predict_interoperability(
        {
            "dataset": dataset,
            "database": {"function": [{"output": [PROTEIN]}]},
            "workflow": {"function": [{"input": [SPECTRUM, PROTEIN]}]},
        },
        {},
    )
    assert result["conclusion"] == expected
    assert result["evidence_coverage"] == coverage


def test_run_predictions_preserve_sources_and_do_not_read_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "configuration.json").write_text(
        json.dumps({"experiments": [{"id": "first"}, {"id": "second"}]})
    )
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "entry.json").write_text('{"operatingSystem":["Linux"]}')
    (metadata / "index.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "experiment": "first",
                        "role": "workflow",
                        "status": "collected",
                        "directory": ".",
                    },
                    {"experiment": "second", "role": "workflow", "status": "not_found"},
                ]
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
    assert first["evidence_coverage"] == 0.5
    assert second["evidence_coverage"] == 0
    assert first["metadata"]["workflow"] == {
        "index": "../metadata/index.json",
        "rows": [0],
        "entry": "../metadata/entry.json",
        "status": "collected",
    }
    assert second["metadata"]["workflow"]["status"] == "not_found"
    assert first["environment"] == "../prediction_environment.json"
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
