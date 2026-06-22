"""Dependency hygiene — deptry (needs the environment to map imports to packages)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import report, run


@pytest.mark.requires_env
def test_deptry(upstream: Path, src_dir: Path, env_ready: bool) -> None:
    """deptry finds no missing / unused / misplaced dependencies.

    deptry needs the project's dependencies installed to resolve import names,
    so it runs in the upstream's resolved environment.
    """
    rel = src_dir.relative_to(upstream) if src_dir != upstream else Path(".")
    proc = run(["uv", "run", "--directory", str(upstream), "--no-dev",
                "--with", "deptry", "deptry", str(rel)])
    assert proc.returncode == 0, report("deptry", proc)
