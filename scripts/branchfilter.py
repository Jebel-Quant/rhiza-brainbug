"""Shared branch-filtering logic for poll.py and build_dashboard.py.

A repo's monitored branches are its branches minus an exclude glob list, and —
if an include list is given — restricted to branches matching it. Patterns are
fnmatch globs (e.g. ``renovate/*``). Filters come from ``repos.yml``:

    defaults:
      branches:
        exclude: ["renovate/*", "dependabot/*"]
        # include: ["main", "release/*"]   # optional allowlist

A per-repo ``branches:`` block fully overrides the defaults for that repo.
"""

from __future__ import annotations

from fnmatch import fnmatch


def resolve_filters(entry: dict, defaults: dict) -> dict:
    """Branch filter for a repo: its own ``branches`` block, else the defaults'."""
    return entry.get("branches") or defaults.get("branches") or {}


def is_monitored(branch: str, filters: dict) -> bool:
    """True if a branch should be polled/tested under the given filter."""
    include = filters.get("include")
    exclude = filters.get("exclude") or []
    if include and not any(fnmatch(branch, p) for p in include):
        return False
    return not any(fnmatch(branch, p) for p in exclude)
