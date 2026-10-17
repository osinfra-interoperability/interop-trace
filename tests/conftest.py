"""Exercise Pooch, Requests and response hooks with an offline HTTP transport."""

from collections.abc import Callable
from io import BytesIO
from typing import Any
from unittest.mock import Mock

import pytest
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
