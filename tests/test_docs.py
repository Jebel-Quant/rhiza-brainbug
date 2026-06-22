"""Docs-coverage check — interrogate against the upstream source (file parsing)."""

from __future__ import annotations

from pathlib import Path

from conftest import DOCS_DEFAULT_FAIL_UNDER, INTERROGATE, report, run


def test_docstring_coverage(upstream: Path, src_dir: Path, pyproject: dict) -> None:
    """Docstring coverage meets the threshold.

    Honours the upstream's own ``[tool.interrogate].fail-under`` if it declares
    one; otherwise applies brainbug's default.
    """
    fail_under = pyproject.get("tool", {}).get("interrogate", {}).get(
        "fail-under", DOCS_DEFAULT_FAIL_UNDER)
    proc = run(["uvx", INTERROGATE, str(src_dir), f"--fail-under={fail_under}", "-q"])
    assert proc.returncode == 0, report(f"interrogate (fail-under={fail_under})", proc)
