"""Security checks — bandit (file parsing) and pip-audit (needs the environment)."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import BANDIT, CONFIG, report, run


def test_bandit(src_dir: Path) -> None:
    """bandit finds no issues in the upstream source."""
    proc = run(["uvx", BANDIT, "-r", str(src_dir), "--ini", str(CONFIG / "bandit.ini"), "-q"])
    assert proc.returncode == 0, report("bandit", proc)


@pytest.mark.requires_env
def test_pip_audit(upstream: Path, env_ready: bool, tmp_path: Path) -> None:
    """pip-audit reports no known-vulnerable dependencies.

    Audits ONLY the upstream's resolved dependency closure: export it to a
    requirements file and audit that, rather than `uv run --with pip-audit`
    (which would also pull pip-audit's own deps — pip, pygments via rich — into
    the audited environment and report their CVEs as false positives).
    """
    reqs = tmp_path / "requirements.txt"
    exp = run(["uv", "export", "--directory", str(upstream), "--no-dev",
               "--format", "requirements-txt", "--no-emit-project", "-q",
               "-o", str(reqs)])
    if exp.returncode != 0:
        pytest.skip("could not export upstream requirements:\n" + report("uv export", exp))
    # --no-deps: the exported file is already the full pinned closure, so audit
    # exactly those pins instead of re-resolving (avoids building a venv).
    proc = run(["uvx", "pip-audit", "-r", str(reqs), "--no-deps"])
    assert proc.returncode == 0, report("pip-audit", proc)
