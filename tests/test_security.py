"""Security checks — bandit (file parsing) and pip-audit (needs the environment)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import BANDIT, CONFIG, report, run, uv_tool


def test_bandit(src_dir: Path) -> None:
    """bandit finds no issues in the upstream source."""
    proc = run(["uvx", BANDIT, "-r", str(src_dir), "--ini", str(CONFIG / "bandit.ini"), "-q"])
    assert proc.returncode == 0, report("bandit", proc)


@pytest.mark.requires_env
def test_pip_audit(upstream: Path, env_ready: bool) -> None:
    """pip-audit reports no known-vulnerable dependencies."""
    proc = uv_tool(upstream, "pip-audit", ["pip-audit"])
    assert proc.returncode == 0, report("pip-audit", proc)
