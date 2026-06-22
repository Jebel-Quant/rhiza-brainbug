"""Static analysis — semgrep using brainbug's ruleset (file parsing)."""

from __future__ import annotations

from pathlib import Path

from conftest import CONFIG, SEMGREP, report, run


def test_semgrep(src_dir: Path) -> None:
    """semgrep finds no rule violations under brainbug's config/semgrep.yml."""
    proc = run(["uvx", SEMGREP, "scan", "--config", str(CONFIG / "semgrep.yml"),
                "--error", "--quiet", "--disable-version-check", str(src_dir)])
    assert proc.returncode == 0, report("semgrep", proc)
