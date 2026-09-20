from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError,
    StreamableHttpTransport,
)


def _redirect_response(location: str) -> MagicMock:
    response = MagicMock()
    response.status_code = 307
    response.headers = {"Location": location}
    return response


def _ok_response() -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    return response


@pytest.mark.parametrize(
    ("endpoint_url", "location", "expected_url"),
    [
        ("http://localhost:8080/mcp", "/mcp/", "http://localhost:8080/mcp/"),
        ("http://localhost/mcp", "https://localhost/mcp/", "https://localhost/mcp/"),
    ],
)
def test_streamable_post_follows_safe_redirect(
    endpoint_url: str, location: str, expected_url: str
) -> None:
    transport = StreamableHttpTransport(endpoint_url)
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": "initialize"}

    with patch(
        "openapi_to_mcp.adapters.testing.http_redirects.requests.post",
        side_effect=[_redirect_response(location), _ok_response()],
    ) as post:
        response = transport._post(payload)

    assert response.status_code == 200
    assert transport.endpoint_url == expected_url
    assert post.call_count == 2
    assert post.call_args_list[0].kwargs["allow_redirects"] is False
    assert post.call_args_list[1].args[0] == expected_url


@pytest.mark.parametrize(
    "location",
    [
        "https://other.example/mcp",
        "http://user:password@localhost:8080/mcp/",
        "http://localhost:8081/mcp",
    ],
)
def test_streamable_post_does_not_follow_unsafe_redirect(location: str) -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.http_redirects.requests.post",
            return_value=_redirect_response(location),
        ) as post,
        pytest.raises(ServerConnectionError, match="redirect was not followed"),
    ):
        transport._post({"jsonrpc": "2.0", "method": "initialize"})

    assert transport.endpoint_url == "http://localhost:8080/mcp"
    post.assert_called_once()


def test_streamable_notification_rejects_a_redirect() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.http_redirects.requests.post",
            return_value=_redirect_response("https://other.example/mcp"),
        ) as post,
        pytest.raises(ServerConnectionError, match="redirect was not followed"),
    ):
        transport._send_initialized_notification()

    post.assert_called_once()


def test_streamable_post_rejects_an_unsafe_second_redirect() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.http_redirects.requests.post",
            side_effect=[
                _redirect_response("/mcp/"),
                _redirect_response("https://other.example/mcp"),
            ],
        ) as post,
        pytest.raises(ServerConnectionError, match="redirect was not followed"),
    ):
        transport._post({"jsonrpc": "2.0", "method": "initialize"})

    assert transport.endpoint_url == "http://localhost:8080/mcp"
    assert post.call_count == 2
