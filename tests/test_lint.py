"""Lint check — ruff against the upstream source using brainbug's shared config."""

from __future__ import annotations

from pathlib import Path

from conftest import CONFIG, RUFF, report, run


def test_ruff(src_dir: Path) -> None:
    """ruff check passes against the upstream source.

    Uses brainbug's central ruff.toml (ported from rhiza) so the standard is
    enforced even for repos that don't carry the config themselves.
    """
    proc = run(["uvx", RUFF, "check", "--config", str(CONFIG / "ruff.toml"),
                "--no-cache", str(src_dir)])
    assert proc.returncode == 0, report("ruff", proc)
