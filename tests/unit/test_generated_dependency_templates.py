"""Contracts for generated Node project dependency templates."""

import json
from pathlib import Path

import jinja2
import pytest

TEMPLATE_DIR = Path(__file__).parents[2] / "openapi_to_mcp" / "templates"


def test_rendered_node_templates_use_supported_dependency_contract() -> None:
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
    )
    package = json.loads(
        environment.get_template("package.json.j2").render(
            server_name="contract-server",
            server_version="1.0.0",
            runtime_validation="input",
            transport="streamable-http",
        )
    )
    tsconfig = json.loads(environment.get_template("tsconfig.json.j2").render())

    assert package["engines"]["node"] == ">=22"
    assert package["dependencies"] == {
        "@modelcontextprotocol/sdk": "^1.30.0",
        "ajv": "^8.20.0",
        "axios": "^1.19.0",
        "dotenv": "^17.4.2",
        "express": "^5.2.1",
    }
    assert package["devDependencies"] == {
        "@types/express": "^5.0.6",
        "@types/node": "^22.20.1",
        "nodemon": "^3.1.14",
        "typescript": "^7.0.2",
    }
    assert tsconfig["compilerOptions"]["rootDir"] == "src"
    assert tsconfig["compilerOptions"]["types"] == ["node"]
    assert tsconfig["compilerOptions"]["outDir"] == "build"


@pytest.mark.parametrize(
    ("runtime_validation", "transport"),
    [
        ("none", "stdio"),
        ("none", "streamable-http"),
        ("input", "stdio"),
        ("input", "streamable-http"),
    ],
)
def test_rendered_package_dependencies_match_enabled_features(
    runtime_validation: str, transport: str
) -> None:
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
    )
    package = json.loads(
        environment.get_template("package.json.j2").render(
            server_name="contract-server",
            server_version="1.0.0",
            runtime_validation=runtime_validation,
            transport=transport,
        )
    )

    dependencies = package["dependencies"]
    dev_dependencies = package["devDependencies"]
    assert ("ajv" in dependencies) == (runtime_validation == "input")
    assert ("express" in dependencies) == (transport == "streamable-http")
    assert ("@types/express" in dev_dependencies) == (transport == "streamable-http")
