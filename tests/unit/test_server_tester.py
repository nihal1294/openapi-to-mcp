from unittest.mock import MagicMock, patch

import pytest
from mcp import MCPError

from openapi_to_mcp.adapters.testing.models import (
    ConnectionSettings,
    ServerTestRequest,
    TransportStrategy,
)
from openapi_to_mcp.adapters.testing.server_tester import (
    StdioTransport,
    StreamableHttpTransport,
    _create_transport_strategy,
    execute_mcp_server,
)


def test_create_transport_strategy_stdio() -> None:
    request = ServerTestRequest(
        transport="stdio",
        method="list",
        connection=ConnectionSettings(server_cmd="node server.js"),
    )

    assert isinstance(_create_transport_strategy(request), StdioTransport)


def test_create_transport_strategy_streamable_http() -> None:
    endpoint_url = "http://localhost:8080/mcp"
    request = ServerTestRequest(
        transport="streamable-http",
        method="list",
        connection=ConnectionSettings(endpoint_url=endpoint_url),
    )

    strategy = _create_transport_strategy(request)

    assert isinstance(strategy, StreamableHttpTransport)
    assert strategy.endpoint_url == endpoint_url


@pytest.mark.parametrize(
    ("test_request", "message"),
    [
        (ServerTestRequest("stdio", "list"), "server_cmd is required"),
        (
            ServerTestRequest("streamable-http", "list"),
            "endpoint_url is required",
        ),
        (ServerTestRequest("invalid", "list"), "Unsupported transport type"),
    ],
)
def test_create_transport_strategy_missing_values(
    test_request: ServerTestRequest, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _create_transport_strategy(test_request)


@pytest.mark.asyncio
async def test_transport_strategy_base_not_implemented() -> None:
    with pytest.raises(
        NotImplementedError, match="Subclasses must implement this method"
    ):
        await TransportStrategy().connect_and_execute("list", None, 1)


@pytest.mark.asyncio
async def test_execute_mcp_server_formats_mcp_error() -> None:
    strategy = MagicMock()
    strategy.connect_and_execute.side_effect = MCPError(
        -32602,
        "bad input",
        {"field": "status"},
    )
    request = ServerTestRequest("stdio", "list")

    with patch(
        "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
        return_value=strategy,
    ):
        response = await execute_mcp_server(request)

    assert response["error"] == {
        "code": -32602,
        "message": "bad input",
        "data": {"field": "status"},
    }


@pytest.mark.asyncio
async def test_execute_mcp_server_reraises_unexpected_error() -> None:
    strategy = MagicMock()
    strategy.connect_and_execute.side_effect = RuntimeError("unexpected")
    request = ServerTestRequest("stdio", "list")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
            return_value=strategy,
        ),
        pytest.raises(RuntimeError, match="unexpected"),
    ):
        await execute_mcp_server(request)
