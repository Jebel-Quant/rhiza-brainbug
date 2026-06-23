"""Static analysis — semgrep using brainbug's ruleset (file parsing)."""

from __future__ import annotations

from pathlib import Path

from conftest import CONFIG, SEMGREP, report, run


def test_semgrep(src_dir: Path) -> None:
    """No ERROR-severity semgrep findings under brainbug's config/semgrep.yml.

    Gates on ERROR (security) rules only. Lower-severity best-practice / style
    rules (e.g. numpy-avoid-inv, WARNING) are advisory and must not fail the
    build — a linalg library legitimately calls np.linalg.inv.
    """
    proc = run(["uvx", SEMGREP, "scan", "--config", str(CONFIG / "semgrep.yml"),
                "--severity", "ERROR", "--error", "--quiet",
                "--disable-version-check", str(src_dir)])
    assert proc.returncode == 0, report("semgrep (ERROR severity)", proc)
