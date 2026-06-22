#!/usr/bin/env python3
"""Poll every branch of every monitored repo and dispatch brainbug runs.

For each repo in repos.yml this script:

  1. lists ALL branches and their head SHAs via the GitHub API,
  2. compares each against the last-seen SHA map in ``state/<owner>__<repo>.json``,
  3. for any branch that is new or changed, fires a ``repository_dispatch`` of
     type ``upstream-commit`` (carrying repo, branch and sha) and updates the map.

Deleted branches drop out of the map automatically (the map is rewritten from
the current branch list each run). The state file is committed back to the repo
by the calling workflow, so state survives between scheduled runs.

Note: this watches every branch, so renovate/dependabot churn produces a run per
branch update. Narrow it later with an include/exclude glob in repos.yml if the
volume is too high.

Env:
    GITHUB_TOKEN     PAT / App token with `repo` scope on brainbug and read
                     access to the monitored repos.
    BRAINBUG_REPO    "owner/repo" of this brainbug repo (e.g. Jebel-Quant/rhiza-brainbug).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml
from branchfilter import is_monitored, resolve_filters

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
API = "https://api.github.com"


def _request(url: str, token: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted host)
        body = resp.read()
        return resp.status, (json.loads(body) if body else None)


def is_archived(owner: str, repo: str, token: str) -> bool:
    """Archived repos are inert — never poll or test them."""
    try:
        _, data = _request(f"{API}/repos/{owner}/{repo}", token)
    except urllib.error.HTTPError as exc:  # pragma: no cover
        print(f"  ! {owner}/{repo}: API error {exc.code}", file=sys.stderr)
        return False  # don't silently drop on a transient error
    return bool(data and data.get("archived"))


def list_branches(owner: str, repo: str, token: str) -> dict[str, str] | None:
    """Return {branch_name: head_sha} for every branch (paginated)."""
    branches: dict[str, str] = {}
    page = 1
    while True:
        url = f"{API}/repos/{owner}/{repo}/branches?per_page=100&page={page}"
        try:
            _, data = _request(url, token)
        except urllib.error.HTTPError as exc:  # pragma: no cover
            print(f"  ! {owner}/{repo}: API error {exc.code}", file=sys.stderr)
            return None
        if not data:
            break
        for b in data:
            branches[b["name"]] = b["commit"]["sha"]
        if len(data) < 100:
            break
        page += 1
    return branches


def dispatch(brainbug: str, token: str, owner: str, repo: str, sha: str, ref: str) -> None:
    url = f"{API}/repos/{brainbug}/dispatches"
    payload = {
        "event_type": "upstream-commit",
        "client_payload": {"repo": f"{owner}/{repo}", "sha": sha, "ref": ref},
    }
    _request(url, token, method="POST", payload=payload)


def main() -> int:
    token = os.environ["GITHUB_TOKEN"]
    brainbug = os.environ["BRAINBUG_REPO"]

    cfg = yaml.safe_load((ROOT / "repos.yml").read_text())
    defaults = cfg.get("defaults", {})

    STATE_DIR.mkdir(exist_ok=True)

    changed = 0
    skipped = 0
    for entry in cfg["repos"]:
        owner, repo = entry["owner"], entry["repo"]

        if is_archived(owner, repo, token):
            print(f"  ~ {owner}/{repo} archived — skipping")
            skipped += 1
            continue

        branches = list_branches(owner, repo, token)
        if not branches:
            continue

        # drop excluded branches (renovate/*, dependabot/*, …) before diffing
        filters = resolve_filters(entry, defaults)
        branches = {b: s for b, s in branches.items() if is_monitored(b, filters)}
        if not branches:
            continue

        cache = STATE_DIR / f"{owner}__{repo}.json"
        try:
            previous = json.loads(cache.read_text()) if cache.exists() else {}
        except (OSError, json.JSONDecodeError):
            previous = {}

        for branch, sha in sorted(branches.items()):
            if previous.get(branch) == sha:
                continue
            old = previous.get(branch)
            print(f"  + {owner}/{repo}@{branch} {(old or 'new')[:8]} -> {sha[:8]} — dispatching")
            dispatch(brainbug, token, owner, repo, sha, branch)
            changed += 1

        # Rewrite the map from the live branch list (prunes deleted branches).
        cache.write_text(json.dumps(branches, indent=2, sort_keys=True) + "\n")

    print(f"done: {changed} branch(es) dispatched, {skipped} archived skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
