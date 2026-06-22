# rhiza-brainbug

Cross-repo test harness. Brainbug **watches a list of repositories** and, when one
of them gets a new commit, **checks out that repo's code and runs brainbug-defined
tests against it** ("brainbugs"). Useful for contract / compatibility / integration
checks that span repos you don't want to duplicate everywhere.

## How a commit in repo B triggers a run in brainbug (A)

Pure polling — nothing is installed in the monitored repos. Brainbug runs on a
cron, compares each repo's latest SHA against the cache in `state/`, and
self-dispatches a run for any that changed.

```
poll.yml (cron) ─▶ poll.py ─▶ diff latest SHA vs state/
                                      │ (changed)
                                      ▼
                            repository_dispatch(upstream-commit)  [self]
                                      ▼
                              on-dispatch.yml
                                      │ (workflow_call)
                                      ▼
                              brainbug.yml
                     checkout upstream@sha + tests/  ─▶ pytest
```

> **Cadence:** routine polling is driven externally by `make loop` (see below),
> because GitHub's `schedule` trigger is best-effort with a ~5-minute floor and
> can't guarantee 1-minute cadence. `poll.yml` is `workflow_dispatch`-only — a
> manual "Run workflow" button for ad-hoc polls.

## Layout

```
repos.yml                       monitored repos + which tests to run
tests/                          the brainbugs — pytest run AGAINST upstream code
scripts/poll.py                 poller for all monitored repos
state/                          last-seen SHA per repo (auto-committed)
.github/workflows/
  brainbug.yml                  reusable: checkout upstream@sha, run tests/
  on-dispatch.yml               on repository_dispatch -> brainbug.yml
  poll.yml                      on schedule -> poll.py
```

## Writing a brainbug

Tests run against the upstream repo checked out at `$UPSTREAM_DIR`. Other env vars:
`UPSTREAM_REPO` (`owner/repo`) and `UPSTREAM_SHA`. See [`tests/test_smoke.py`](tests/test_smoke.py).

```python
def test_thing(upstream):           # upstream = Path to checked-out repo
    assert (upstream / "pyproject.toml").exists()
```

## Status dashboard (GitHub Pages)

A static dashboard shows each monitored repo's latest commit and its most recent
brainbug verdict. It's generated **server-side** by `scripts/build_dashboard.py`
(brainbug is private, so a browser couldn't read its runs directly) and published
to Pages by `.github/workflows/pages.yml` — rebuilt after every brainbug run, on
pushes to `main`, and every 30 min.

Enable once: **Settings → Pages → Source: GitHub Actions** (or
`gh api -X POST repos/<owner>/<repo>/pages -f build_type=workflow`), then run the
`pages` workflow. Verdicts appear as repos get tested under the new run naming.

## Setup checklist

1. **Create the repo** `Jebel-Quant/rhiza-brainbug` and push this skeleton.
2. **Add a secret** `BRAINBUG_PAT` to brainbug — a PAT (or fine-grained token) with
   `repo` scope. Needed to read private monitored repos; the default
   `GITHUB_TOKEN` can self-dispatch and read public repos but not private ones.
3. **Adjust the cron** in `.github/workflows/poll.yml` to taste (see cadence
   caveat above).
4. Replace `tests/test_smoke.py` with real brainbugs.

## Run locally

```bash
pip install -e .
UPSTREAM_DIR=/path/to/some/checkout pytest tests/ -v
```

## Run the poller externally (true 1-minute cadence)

Since GitHub's `schedule` can't reliably poll every minute, run the loop from any
always-on machine (laptop, VM, container) via the [`Makefile`](Makefile):

```bash
export GITHUB_TOKEN=ghp_...            # PAT with `repo` scope
make loop                              # poll every 60s forever
make loop INTERVAL=30                  # or every 30s
make poll                              # one-shot
```

The loop keeps its last-seen SHAs in the local `state/` dir, independent of the
SHA cache the Actions `poll.yml` commits — so pick **one** runner (Actions *or*
the local loop) as the source of truth to avoid double-dispatching the same commit.

