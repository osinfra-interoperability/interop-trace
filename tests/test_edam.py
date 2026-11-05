"""Check directional named-class matching against a small offline ontology."""

from pathlib import Path

import pytest

from interop_trace.edam import Edam


@pytest.mark.parametrize(
    "output,accepted,path",
    [
        ("data_2976", "data_0006", ["data_2976", "data_2044", "data_0006"]),
        ("data_2976", "data_2976", ["data_2976"]),
        ("data_0006", "data_2976", None),
        ("data_0943", "data_2976", None),
        ("format_3244", "format_1915", ["format_3244", "format_1915"]),
        ("format_9999", "format_9999", None),
        ("data_9999", "data_9999", None),
    ],
)
def test_directional_paths(edam_path: Path, output, accepted, path) -> None:
    ontology = Edam.from_file(edam_path)
    assert ontology.match(
        f"https://edamontology.org/{output}",
        f"http://edamontology.org/{accepted}",
        output.split("_")[0],
    ) == ([f"http://edamontology.org/{term}" for term in path] if path else None)
