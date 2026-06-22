"""TODO/FIXME/HACK report — advisory (never fails the build)."""

from __future__ import annotations

import re
from pathlib import Path

MARKER = re.compile(r"\b(TODO|FIXME|HACK)\b")
SKIP_DIRS = {".git", ".venv", "node_modules", ".tox", "build", "dist", "__pycache__"}
EXTS = {".py", ".md", ".sh", ".yml", ".yaml", ".toml", ".cfg"}


def test_todos_report(upstream: Path) -> None:
    """Count TODO/FIXME/HACK markers and report them; always passes.

    Mirrors rhiza's `make todos` — informational visibility, not a gate.
    """
    hits = []
    for path in upstream.rglob("*"):
        if not path.is_file() or path.suffix not in EXTS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if MARKER.search(line):
                    hits.append(f"{path.relative_to(upstream)}:{n}: {line.strip()[:100]}")
        except OSError:
            continue
    print(f"\n{len(hits)} TODO/FIXME/HACK marker(s)")
    for h in hits[:50]:
        print("  " + h)
    assert True  # advisory only
