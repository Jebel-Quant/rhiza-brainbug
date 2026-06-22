"""Sample brainbug test.

Brainbug tests run *against an upstream repository's checked-out code*, not
against brainbug itself. The workflow checks out the upstream repo at the
triggering SHA into ``$UPSTREAM_DIR`` and exposes a few env vars:

    UPSTREAM_DIR    absolute path to the checked-out upstream repo
    UPSTREAM_REPO   "owner/repo"
    UPSTREAM_SHA    the commit SHA that triggered this run

Write whatever cross-repo / compatibility / contract checks you need here.
Replace this smoke test with real "brainbugs".
"""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def upstream() -> Path:
    """Path to the checked-out upstream repository."""
    root = os.environ.get("UPSTREAM_DIR")
    if not root:
        pytest.skip("UPSTREAM_DIR not set — run via the brainbug workflow")
    path = Path(root)
    assert path.is_dir(), f"UPSTREAM_DIR does not exist: {path}"
    return path


def test_upstream_checked_out(upstream: Path) -> None:
    """The upstream repo was checked out and looks like a git repo."""
    assert (upstream / ".git").exists()


def test_has_python_project(upstream: Path) -> None:
    """Example contract: every monitored repo should ship a pyproject.toml."""
    assert (upstream / "pyproject.toml").exists(), (
        f"{os.environ.get('UPSTREAM_REPO')} is missing pyproject.toml"
    )
