"""Offline HTTP transport and a minimal experiment catalogue."""

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse


@pytest.fixture
def http_response() -> Callable[..., Response]:
    def make(
        body: bytes, headers: dict[str, str] | None = None, status: int = 200
    ) -> Response:
        response = Response()
        response.status_code = status
        response.headers.update(headers or {})
        response.raw = HTTPResponse(
            body=BytesIO(body), headers=headers, preload_content=False
        )
        return response

    return make


@pytest.fixture(autouse=True)
def http_transport(
    monkeypatch: pytest.MonkeyPatch, http_response: Callable[..., Response]
) -> Mock:
    transport = Mock(side_effect=lambda request: http_response(request.url.encode()))

    def send(adapter: HTTPAdapter, request: PreparedRequest, **_: Any) -> Response:
        response: Response = transport(request)
        response.request = request
        response.url = request.url
        return response

    monkeypatch.setattr(HTTPAdapter, "send", send)
    return transport


@pytest.fixture
def configuration(tmp_path: Path) -> Path:
    """One synthetic experiment with reusable profiles; no external resources."""
    directory = tmp_path / "experiments" / "components"
    directory.mkdir(parents=True)
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
            "type": "expected_peptides",
            "parameters": {"peptides": ["PEPTIDE"]},
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
    path = directory.parent / "run.yaml"
    path.write_text(yaml.safe_dump(document))
    return path
