#!/usr/bin/env python3
"""Build a static status dashboard for the monitored repos.

Runs server-side (in CI, with a token) and renders a self-contained
``site/index.html`` that needs no client-side API calls — so it works even
though brainbug itself is private. For each repo in repos.yml it shows:

  * the upstream repo's latest commit (sha, message, author, when),
  * the last brainbug verdict for that repo (from on-dispatch.yml run names),
  * whether brainbug has tested the latest commit yet.

Env:
    GITHUB_TOKEN   token with read access (default Actions token is enough for
                   public monitored repos + brainbug's own Actions).
    BRAINBUG_REPO  "owner/repo" of this repo (defaults to Jebel-Quant/rhiza-brainbug).
    BUILT_AT       ISO timestamp to stamp the page (optional; CI passes one).
"""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import yaml
from branchfilter import is_monitored, resolve_filters

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "index.html"
API = "https://api.github.com"


def api(path: str, token: str):
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"  ! {path}: {exc.code}")
        return None


def branch_names(full: str, token: str) -> list[str]:
    """Branch names for a repo (first 100 — enough for a display count)."""
    data = api(f"/repos/{full}/branches?per_page=100", token)
    return [b["name"] for b in (data or [])]


def branch_has_pyproject(full: str, ref: str, token: str) -> bool:
    """True if a branch carries pyproject.toml (quiet — no error logging).

    Branches without one (paper/docs/LaTeX) aren't Python targets, so they
    shouldn't be counted as failing on the dashboard.
    """
    req = urllib.request.Request(f"{API}/repos/{full}/contents/pyproject.toml?ref={ref}")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req):  # noqa: S310
            return True
    except urllib.error.HTTPError as exc:
        return exc.code != 404  # permissive on transient/other errors


def latest_verdicts(brainbug: str, token: str) -> dict[str, dict[str, dict]]:
    """Map 'owner/repo' -> {branch -> latest run {conclusion, url, sha, branch, when}}.

    Run names are "brainbug · owner/repo · branch · sha" (older runs omit the
    branch: "brainbug · owner/repo · sha"). Runs arrive newest-first, so the first
    run seen per (repo, branch) is that branch's latest. Paginated because the
    monitored repos have many branches.
    """
    out: dict[str, dict[str, dict]] = {}
    for page in range(1, 6):  # up to 500 runs
        data = api(
            f"/repos/{brainbug}/actions/workflows/on-dispatch.yml/runs"
            f"?per_page=100&page={page}",
            token,
        )
        runs = (data or {}).get("workflow_runs", [])
        if not runs:
            break
        for run in runs:
            parts = [p.strip() for p in run.get("name", "").split("·")]
            if len(parts) == 4:
                repo, branch, sha = parts[1], parts[2], parts[3]
            elif len(parts) == 3:
                repo, branch, sha = parts[1], "(legacy)", parts[2]
            else:
                continue
            per_branch = out.setdefault(repo, {})
            if branch in per_branch:  # already have this branch's newest
                continue
            per_branch[branch] = {
                "conclusion": run.get("conclusion") or run.get("status"),
                "url": run.get("html_url"),
                "sha": sha,
                "branch": branch,
                "when": run.get("created_at"),
            }
    return out


STATUS = {
    "success": ("ok", "passing"),
    "failure": ("bad", "failing"),
    "cancelled": ("warn", "cancelled"),
    "in_progress": ("warn", "running"),
    "queued": ("warn", "queued"),
    None: ("none", "never run"),
}


def card(entry: dict, meta: dict, commit: dict | None, verdict: dict | None,
         branches: list[str] | None = None, failing: list[str] | None = None,
         archived: bool = False) -> str:
    full = f"{entry['owner']}/{entry['repo']}"
    cls, label = STATUS.get((verdict or {}).get("conclusion"), ("none", "unknown"))

    if archived:
        # Archived repos are inert — greyed out, never polled or tested.
        return f"""    <div class="card archived" data-name="{html.escape(full.lower())}">
      <div class="row">
        <a class="name" href="https://github.com/{full}">{html.escape(full)}</a>
        <span class="badge none">archived</span>
      </div>
      <div class="commit"><span class="msg dim">archived — not polled or tested</span></div>
    </div>"""

    # brainbug monitors every branch — badge follows the default branch; show the
    # branch count plus how many branches are currently failing.
    branches = branches or []
    failing = failing or []
    n = len(branches)
    label_txt = "branch" if n == 1 else "branches"
    branch_title = "monitored branches: " + (", ".join(branches[:40]) if branches else "—")
    branch_html = (f'<span class="branch" title="{html.escape(branch_title)}">'
                   f'⎇ {n} {label_txt}</span>')
    if failing:
        fail_title = "failing branches: " + ", ".join(sorted(failing)[:40])
        branch_html += (f'<span class="branch failcount" title="{html.escape(fail_title)}">'
                        f'{len(failing)} failing</span>')

    # description
    desc = (meta.get("description") or "").strip()
    desc_html = f'<div class="desc">{html.escape(desc[:110])}</div>' if desc else ""

    # latest commit
    if commit:
        c = commit["commit"]
        msg = html.escape(c["message"].splitlines()[0][:72])
        sha = commit["sha"][:7]
        when = c["committer"]["date"][:10]
        gh_user = commit.get("author")
        author = html.escape(gh_user["login"] if gh_user else c["author"]["name"])
        commit_html = (
            f'<a class="sha" href="{html.escape(commit["html_url"])}">{sha}</a> '
            f'<span class="msg">{msg}</span>'
            f'<div class="meta">{author} · {when}</div>'
        )
    else:
        commit_html = '<span class="msg dim">commit unavailable</span>'

    # repo stats (from metadata already fetched)
    lang = meta.get("language")
    stats = [
        f'<span class="stat" title="stars">★ {meta.get("stargazers_count", 0)}</span>',
        f'<span class="stat" title="forks">⑂ {meta.get("forks_count", 0)}</span>',
        f'<span class="stat" title="open issues &amp; PRs">⊙ {meta.get("open_issues_count", 0)}</span>',
    ]
    if lang:
        stats.append(f'<span class="stat lang">{html.escape(lang)}</span>')
    if meta.get("pushed_at"):
        stats.append(f'<span class="stat">pushed {meta["pushed_at"][:10]}</span>')
    stats_html = f'<div class="stats">{"".join(stats)}</div>'

    # brainbug verdict line — names the branch+sha of the most recent run
    if verdict:
        vwhen = (verdict.get("when") or "")[:10]
        vbranch = verdict.get("branch")
        vsha = (verdict.get("sha") or "")[:7]
        where = f"{vbranch}@{vsha}" if vbranch else vsha
        tag = f'<span class="tag tested">last run · {html.escape(where)}</span>'
        verdict_html = f'<div class="verdict">{tag}<span class="vwhen">{vwhen}</span></div>'
    else:
        verdict_html = ""

    vurl = (verdict or {}).get("url")
    badge = f'<a class="badge {cls}" href="{html.escape(vurl)}">{label}</a>' if vurl \
        else f'<span class="badge {cls}">{label}</span>'

    return f"""    <div class="card" data-name="{html.escape(full.lower())}">
      <div class="row">
        <div class="title"><a class="name" href="https://github.com/{full}">{html.escape(full)}</a>{branch_html}</div>
        {badge}
      </div>
      {desc_html}
      <div class="commit">{commit_html}</div>
      {stats_html}
      {verdict_html}
    </div>"""


def main() -> int:
    token = os.environ["GITHUB_TOKEN"]
    brainbug = os.environ.get("BRAINBUG_REPO", "Jebel-Quant/rhiza-brainbug")
    built_at = os.environ.get("BUILT_AT", "")

    cfg = yaml.safe_load((ROOT / "repos.yml").read_text())
    defaults = cfg.get("defaults", {})

    print("fetching brainbug verdicts...")
    verdicts = latest_verdicts(brainbug, token)

    cards = []
    counts = {"ok": 0, "bad": 0, "other": 0, "archived": 0}
    for entry in cfg["repos"]:
        full = f"{entry['owner']}/{entry['repo']}"
        meta = api(f"/repos/{full}", token) or {}
        archived = bool(meta.get("archived"))
        print(f"  {full}{' [archived]' if archived else ''}")
        if archived:
            cards.append(card(entry, meta, None, None, archived=True))
            counts["archived"] += 1
            continue
        filters = resolve_filters(entry, defaults)
        branches = [b for b in branch_names(full, token) if is_monitored(b, filters)]
        head = meta.get("default_branch") or "main"
        commit = api(f"/repos/{full}/commits/{head}", token)
        # Badge follows the DEFAULT branch; count other CURRENTLY-MONITORED
        # branches that are failing (ignore stale verdicts for gone branches).
        repo_verdicts = verdicts.get(full, {})
        verdict = repo_verdicts.get(head)
        monitored = set(branches)
        failing = [b for b, v in repo_verdicts.items()
                   if b != head and b in monitored and v.get("conclusion") == "failure"]
        # don't count branches that aren't Python targets (no pyproject.toml)
        failing = [b for b in failing if branch_has_pyproject(full, b, token)]
        cards.append(card(entry, meta, commit, verdict, branches=branches, failing=failing))
        c = (verdict or {}).get("conclusion")
        counts["ok" if c == "success" else "bad" if c == "failure" else "other"] += 1

    page = TEMPLATE.format(
        brainbug=html.escape(brainbug),
        total=len(cfg["repos"]),
        ok=counts["ok"],
        bad=counts["bad"],
        other=counts["other"],
        archived=counts["archived"],
        built_at=html.escape(built_at),
        cards="\n".join(cards),
        script=SCRIPT,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(cfg['repos'])} repos)")
    return 0


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="900">
<title>rhiza-brainbug · monitored repos</title>
<style>
  :root {{
    --bg:#0d1117; --panel:#161b22; --border:#30363d; --fg:#e6edf3; --dim:#8b949e;
    --ok:#3fb950; --bad:#f85149; --warn:#d29922; --none:#6e7681;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
  header {{ padding:28px 20px 12px; max-width:1200px; margin:0 auto; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  h1 .mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--dim); }}
  .summary {{ color:var(--dim); font-size:13px; }}
  .summary b.ok {{ color:var(--ok); }} .summary b.bad {{ color:var(--bad); }}
  #search {{ margin-top:14px; width:100%; max-width:420px; background:var(--panel);
    color:var(--fg); border:1px solid var(--border); border-radius:8px;
    padding:8px 12px; font-size:14px; outline:none; }}
  #search:focus {{ border-color:#58a6ff; }}
  #search::placeholder {{ color:var(--none); }}
  #shown {{ margin-left:10px; color:var(--dim); font-size:12px; }}
  main {{ max-width:1200px; margin:0 auto; padding:8px 20px 48px;
    display:grid; grid-template-columns:repeat(2,1fr); gap:16px; }}
  @media (max-width:760px) {{ main {{ grid-template-columns:1fr; }} }}
  .card {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px 16px; }}
  .card.archived {{ opacity:.5; filter:grayscale(1); background:#10141a; border-style:dashed; }}
  .card.archived .name {{ color:var(--dim); }}
  .row {{ display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }}
  .title {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .name {{ font-weight:600; color:var(--fg); text-decoration:none; }}
  .name:hover {{ text-decoration:underline; }}
  .branch {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11px;
    color:var(--dim); background:rgba(110,118,129,.15); padding:1px 7px; border-radius:20px; }}
  .branch.mismatch {{ color:var(--warn); background:rgba(210,153,34,.15); }}
  .branch.failcount {{ color:var(--bad); background:rgba(248,81,73,.15); }}
  .badge {{ font-size:11px; font-weight:600; padding:2px 9px; border-radius:20px;
    text-decoration:none; white-space:nowrap; }}
  .badge.ok {{ background:rgba(63,185,80,.15); color:var(--ok); }}
  .badge.bad {{ background:rgba(248,81,73,.15); color:var(--bad); }}
  .badge.warn {{ background:rgba(210,153,34,.15); color:var(--warn); }}
  .badge.none {{ background:rgba(110,118,129,.15); color:var(--none); }}
  .desc {{ margin-top:6px; font-size:12.5px; color:var(--dim); }}
  .commit {{ margin-top:10px; font-size:13px; }}
  .sha {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:#58a6ff; text-decoration:none; }}
  .msg {{ color:var(--fg); }} .msg.dim, .dim {{ color:var(--dim); }}
  .meta {{ color:var(--dim); font-size:12px; margin-top:3px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:11px; padding-top:10px;
    border-top:1px solid var(--border); font-size:12px; color:var(--dim); }}
  .stat {{ white-space:nowrap; }}
  .stat.lang {{ color:#58a6ff; }}
  .verdict {{ display:flex; align-items:center; gap:8px; margin-top:9px; }}
  .vwhen {{ color:var(--dim); font-size:11px; }}
  .tag {{ display:inline-block; font-size:11px; padding:1px 8px; border-radius:4px; }}
  .tag.fresh {{ color:var(--ok); border:1px solid rgba(63,185,80,.4); }}
  .tag.stale {{ color:var(--warn); border:1px solid rgba(210,153,34,.4); }}
  .tag.tested {{ color:var(--dim); border:1px solid var(--border);
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
  footer {{ max-width:1200px; margin:0 auto; padding:0 20px 40px; color:var(--dim); font-size:12px; }}
</style>
</head>
<body>
<header>
  <h1>brainbug <span class="mono">· monitored repos</span></h1>
  <div class="summary">
    {total} repos · <b class="ok">{ok} passing</b> · <b class="bad">{bad} failing</b> · {other} other · {archived} archived
  </div>
  <input id="search" type="search" autocomplete="off" spellcheck="false"
         placeholder="filter repos…  e.g.  cvxgrp*   linalg   tschm/">
  <span id="shown"></span>
</header>
<main>
{cards}
</main>
<footer>
  Generated by <span class="mono">{brainbug}</span> · {built_at} · auto-refreshes every 15 min
</footer>
{script}
</body>
</html>
"""


# Client-side card filter. Kept out of TEMPLATE.format() so its braces don't need
# escaping. Matches the card's data-name (owner/repo, lowercased): space-separated
# terms are OR'd; a term with '*' is a glob (anchored), otherwise it's a substring.
SCRIPT = r"""<script>
  (function () {
    var box = document.getElementById('search');
    var shown = document.getElementById('shown');
    var cards = Array.prototype.slice.call(document.querySelectorAll('.card'));
    function termToRe(t) {
      var esc = t.replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*');
      return new RegExp(t.indexOf('*') >= 0 ? '^' + esc + '$' : esc);
    }
    function apply() {
      var q = box.value.trim().toLowerCase();
      var terms = q ? q.split(/\s+/).map(termToRe) : null;
      var n = 0;
      cards.forEach(function (c) {
        var name = c.getAttribute('data-name') || '';
        var vis = !terms || terms.some(function (re) { return re.test(name); });
        c.style.display = vis ? '' : 'none';
        if (vis) n++;
      });
      shown.textContent = terms ? (n + ' shown') : '';
    }
    box.addEventListener('input', apply);
  })();
</script>"""


if __name__ == "__main__":
    raise SystemExit(main())
