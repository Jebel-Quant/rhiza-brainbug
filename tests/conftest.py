"""Shared fixtures and helpers for the brainbug check battery.

Checks run against an upstream repository checked out at ``$UPSTREAM_DIR`` (set
by .github/workflows/brainbug.yml). Two families:

  * file-parsing checks (ruff, bandit, interrogate, semgrep, pyproject, todos)
    shell out to ``uvx`` and need no dependency install;
  * environment checks (pip-audit, pip-licenses, deptry) need the upstream's
    dependencies resolved, so they run via ``uv run --directory`` and are marked
    ``requires_env`` — deselect with ``-m "not requires_env"``.

Tool versions are pinned to match rhiza's pre-commit / make targets.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

# brainbug repo root (this file is tests/conftest.py)
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"

# Tool pins (kept in sync with rhiza's .pre-commit-config.yaml / make.d)
RUFF = "ruff@0.15.18"
BANDIT = "bandit@1.9.4"
INTERROGATE = "interrogate@1.7.0"
SEMGREP = "semgrep"  # latest; rhiza tracks the moving release

# license families that fail compliance (matches rhiza LICENSE_FAIL_ON)
LICENSE_FAIL_ON = "GPL;LGPL;AGPL"
# default docstring-coverage threshold when the upstream declares none
DOCS_DEFAULT_FAIL_UNDER = 80


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    """Run a command, capturing output; never raises on non-zero exit."""
    return subprocess.run(  # noqa: S603
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )


def report(label: str, proc: subprocess.CompletedProcess) -> str:
    """Format command output for an assertion message."""
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return f"{label} exited {proc.returncode}\n--- stdout ---\n{out}\n--- stderr ---\n{err}"


@pytest.fixture(scope="session")
def upstream() -> Path:
    """Path to the checked-out upstream repository."""
    root = os.environ.get("UPSTREAM_DIR")
    if not root:
        pytest.skip("UPSTREAM_DIR not set — run via the brainbug workflow")
    path = Path(root)
    assert path.is_dir(), f"UPSTREAM_DIR does not exist: {path}"
    return path


@pytest.fixture(scope="session")
def upstream_name() -> str:
    """owner/repo of the upstream under test (informational)."""
    return os.environ.get("UPSTREAM_REPO", "<unknown>")


@pytest.fixture(scope="session")
def pyproject(upstream: Path) -> dict:
    """Parsed pyproject.toml of the upstream (skips checks if absent)."""
    f = upstream / "pyproject.toml"
    if not f.exists():
        pytest.skip("upstream has no pyproject.toml")
    return tomllib.loads(f.read_text())


@pytest.fixture(scope="session")
def src_dir(upstream: Path) -> Path:
    """Best-guess source directory of the upstream.

    Prefers ``src/``; else a top-level importable package (has __init__.py and
    is not tests/docs/etc.); else falls back to the repo root.
    """
    if (upstream / "src").is_dir():
        return upstream / "src"
    skip = {"tests", "test", "docs", "doc", "examples", "notebooks", "book",
            ".venv", ".git", "build", "dist"}
    candidates = [
        d for d in sorted(upstream.iterdir())
        if d.is_dir() and d.name not in skip and not d.name.startswith(".")
        and (d / "__init__.py").exists()
    ]
    return candidates[0] if candidates else upstream


@pytest.fixture(scope="session")
def env_ready(upstream: Path) -> bool:
    """Resolve the upstream's environment once; skip env checks if it fails.

    Running ``uv run`` here triggers dependency resolution + install for the
    upstream project. If that fails (no build backend, unresolvable deps, …) we
    skip the environment checks rather than reporting a false finding.
    """
    if not (upstream / "pyproject.toml").exists():
        pytest.skip("no pyproject.toml — cannot build upstream environment")
    proc = run(["uv", "run", "--directory", str(upstream), "--no-dev",
                "python", "-c", "pass"])
    if proc.returncode != 0:
        pytest.skip("upstream environment could not be resolved:\n" + report("uv run", proc))
    return True


def uv_tool(upstream: Path, with_pkg: str, args: list[str]) -> subprocess.CompletedProcess:
    """Run a tool in the upstream's resolved environment via ``uv run``."""
    return run(["uv", "run", "--directory", str(upstream), "--no-dev",
                "--with", with_pkg, *args])
