from pathlib import Path
from unittest.mock import MagicMock

import jinja2

from openapi_to_mcp.adapters.generator import Generator
from tests.utils import setup_path_mocks


def test_generator_selects_streamable_http_transport_template(
    mocker: MagicMock,
) -> None:
    output_dir = "fake/output"
    context = {
        "server_name": "test-server",
        "tools": [],
        "transport": "streamable-http",
    }

    setup_path_mocks(mocker, output_dir)
    gen = Generator(output_dir=output_dir, context=context)
    gen.env = MagicMock(spec=jinja2.Environment)

    mock_render = mocker.patch.object(gen, "_render_and_write")
    transport_output = MagicMock(spec=Path)
    gen.output_path.__truediv__.return_value = transport_output

    gen._generate_transport_file()

    gen.output_path.__truediv__.assert_called_once_with("src")
    transport_output.__truediv__.assert_called_once_with("transport.ts")
    mock_render.assert_called_once_with(
        "src/transport_streamable_http.ts.j2",
        transport_output.__truediv__.return_value,
    )
