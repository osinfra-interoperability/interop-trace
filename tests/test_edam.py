"""Check directional named-class matching against a small offline ontology."""

import json
from pathlib import Path

import pytest

from interop_trace.edam import Edam


@pytest.mark.parametrize(
    "output,accepted,relation",
    [
        ("data_2976", "data_0006", "subclass"),
        ("data_2976", "data_2976", "identity"),
        ("data_0006", "data_2976", None),
        ("data_0943", "data_2976", None),
        ("format_3244", "format_1915", "subclass"),
        ("format_9999", "format_9999", None),
        ("data_9999", "data_9999", None),
    ],
)
def test_directional_relations(edam_path: Path, output, accepted, relation) -> None:
    ontology = Edam.from_responses(json.loads(edam_path.read_text()))
    assert (
        ontology.match(
            f"https://edamontology.org/{output}",
            f"http://edamontology.org/{accepted}",
            output.split("_")[0],
        )
        == relation
    )
