import tomllib
from pathlib import Path


def test_ruff_version() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert "ruff==0.16.4" in config["dependency-groups"]["dev"]


def test_hatchling_version() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert config["build-system"]["requires"] == ["hatchling==1.32.0"]
