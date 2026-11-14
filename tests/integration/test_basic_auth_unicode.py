"""Emitted environment names must authenticate schemes with non-ASCII names."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.basic_auth_support import build_basic_project, run_auth_case

if TYPE_CHECKING:
    from pathlib import Path


def test_emitted_env_names_authenticate_non_ascii_basic_scheme(tmp_path: Path) -> None:
    output = build_basic_project(tmp_path / "generated", "Básic-Auth")
    names = [
        line.split("=", 1)[0]
        for line in (output / ".env.example").read_text().splitlines()
        if line.startswith("AUTH_")
        and line.split("=", 1)[0].endswith(("_USERNAME", "_PASSWORD"))
    ]
    env = {
        name: "unicode-wire-user"
        if name.endswith("_USERNAME")
        else "unicode-wire-password"
        for name in names
    }
    capture, _ = run_auth_case(output, {"env": env})
    assert len(capture["requests"]) == 1, capture["result"]
    assert not capture["result"].get("isError", False)
    assert sorted(names) == ["AUTH_B_SIC_AUTH_PASSWORD", "AUTH_B_SIC_AUTH_USERNAME"]
