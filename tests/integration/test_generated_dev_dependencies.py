"""The patched development matcher must preserve generated watch behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

from scripts.generated_dependency_audit import render_manifest

if TYPE_CHECKING:
    from pathlib import Path


def test_generated_nodemon_uses_patched_compatible_glob_matcher(tmp_path: Path) -> None:
    manifest = render_manifest("stdio", "none")
    (tmp_path / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    npm = shutil.which("npm")
    node = shutil.which("node")
    assert npm is not None
    assert node is not None
    installed = subprocess.run(  # noqa: S603
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    script = """
const path = require('node:path');
const match = require('nodemon/lib/monitor/match');
const nodemon = path.dirname(require.resolve('nodemon/package.json'));
const version = require(require.resolve('minimatch/package.json', { paths: [nodemon] })).version;
const files = ['src/index.ts', 'src/cache.json', 'node_modules/other/index.ts'];
const matched = match(files, ['src/**', '!**/node_modules/**'], 'ts');
console.log(JSON.stringify({version, files: matched.result.map(p => path.relative(process.cwd(), p))}));
"""
    checked = subprocess.run(  # noqa: S603
        [node, "--input-type=commonjs", "--eval", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    result = json.loads(checked.stdout)
    assert result["version"].startswith("11.")
    assert result["files"] == ["src/index.ts"]
