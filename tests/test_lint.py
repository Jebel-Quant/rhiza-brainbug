"""Lint check — ruff against the upstream source using brainbug's shared config."""

from __future__ import annotations

from pathlib import Path

from conftest import CONFIG, RUFF, python_target, report, run


def test_ruff(src_dir: Path, pyproject: dict) -> None:
    """ruff check passes against the upstream source.

    Uses brainbug's central ruff.toml (ported from rhiza) so the standard is
    enforced even for repos that don't carry the config themselves, but with
    --target-version derived from the upstream's own minimum Python so modern
    syntax (e.g. PEP 695 generics, 3.12+) isn't misread as a syntax error.
    """
    proc = run(["uvx", RUFF, "check", "--config", str(CONFIG / "ruff.toml"),
                "--target-version", python_target(pyproject),
                "--no-cache", str(src_dir)])
    assert proc.returncode == 0, report("ruff", proc)
