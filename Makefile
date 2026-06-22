# rhiza-brainbug — run the poller from an external cron / always-on runner.
#
# The GitHub Actions `schedule` trigger can't reliably do 1-minute cadence, so
# for true 1-minute polling run the loop here instead (laptop, VM, container…).
#
# Required env:
#   GITHUB_TOKEN   PAT with `repo` scope (read monitored repos + dispatch brainbug)
# Optional env (with defaults):
#   BRAINBUG_REPO  target repo for self-dispatch     (default below)
#   INTERVAL       seconds between polls in `loop`    (default 60)
#   PYTHON         interpreter                        (default python3)

BRAINBUG_REPO ?= Jebel-Quant/rhiza-brainbug
INTERVAL      ?= 60
PYTHON        ?= python3

export BRAINBUG_REPO

.PHONY: help install test poll loop check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies (pytest, pyyaml)
	$(PYTHON) -m pip install -e .

test: ## Run brainbug tests (set UPSTREAM_DIR to a checked-out repo)
	$(PYTHON) -m pytest tests/ -v

check: ## Fail unless GITHUB_TOKEN is set
	@test -n "$$GITHUB_TOKEN" || { echo "ERROR: GITHUB_TOKEN is not set"; exit 1; }

poll: check ## Poll all repos once and dispatch any that changed
	$(PYTHON) scripts/poll.py

loop: check ## Poll every $(INTERVAL)s forever (Ctrl-C to stop)
	@echo "Polling $(BRAINBUG_REPO) every $(INTERVAL)s — Ctrl-C to stop"
	@while true; do \
		$(PYTHON) scripts/poll.py || echo "poll failed (retrying next tick)"; \
		sleep $(INTERVAL); \
	done
