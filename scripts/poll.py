#!/usr/bin/env python3
"""Poll monitored repos for new commits and dispatch brainbug runs.

For every repo in repos.yml this script:

  1. asks the GitHub API for the latest commit SHA on the tracked ref,
  2. compares it against the last-seen SHA cached in ``state/<owner>__<repo>``,
  3. if changed (or never seen), fires a ``repository_dispatch`` of type
     ``upstream-commit`` at this brainbug repo and updates the cache.

The cache is committed back to the repo by the calling workflow, so state
survives between scheduled runs without any external storage.

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


def latest_sha(owner: str, repo: str, ref: str, token: str) -> str | None:
    url = f"{API}/repos/{owner}/{repo}/commits/{ref}"
    try:
        _, data = _request(url, token)
    except urllib.error.HTTPError as exc:  # pragma: no cover
        print(f"  ! {owner}/{repo}: API error {exc.code}", file=sys.stderr)
        return None
    return data["sha"] if data else None


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
    default_ref = defaults.get("ref", "main")

    STATE_DIR.mkdir(exist_ok=True)

    changed = 0
    for entry in cfg["repos"]:
        owner, repo = entry["owner"], entry["repo"]
        ref = entry.get("ref", default_ref)

        sha = latest_sha(owner, repo, ref, token)
        if not sha:
            continue

        cache = STATE_DIR / f"{owner}__{repo}"
        previous = cache.read_text().strip() if cache.exists() else None

        if sha == previous:
            print(f"  = {owner}/{repo} unchanged ({sha[:8]})")
            continue

        print(f"  + {owner}/{repo} changed {(previous or 'new')[:8]} -> {sha[:8]} — dispatching")
        dispatch(brainbug, token, owner, repo, sha, ref)
        cache.write_text(sha + "\n")
        changed += 1

    print(f"done: {changed} repo(s) dispatched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
