# OAuth Migration (subscription auth) Implementation Plan

> **Status:** Plan audit-loop stabilised after 3 consecutive zero-finding rounds.

**Goal:** Migrate the PR review bot + reviewer cron from Anthropic SDK + `ANTHROPIC_API_KEY` (pay-per-token billing) to `claude` CLI subprocess + `CLAUDE_CODE_OAUTH_TOKEN` (Claude Code Pro/Max subscription billing).

**Architecture:** Replace the `anthropic.Anthropic().messages.create()` call in `tools/pr_review/__main__.py::call_claude()` and `tools/pr_review/cron.py::claude_generate_patch()` with `subprocess.run(["claude", "-p", user, "--append-system-prompt", system])`. Workflows install `claude` via npm and pass `CLAUDE_CODE_OAUTH_TOKEN` instead of `ANTHROPIC_API_KEY`.

**Tech stack:** Python `subprocess`, `claude` CLI 2.x, GitHub Actions, npm.

---

## Audit Evidence

### Repository state verified before planning
- Latest origin/main: `f922190 feat: reviewer cron (v1) — every 6h iterates open PRs and acts on verdicts (#19)`
- `pytest -q orchestrator/tests` → 63 passed
- `ruff check .` → clean
- Local `claude` CLI: `/Users/i.a.s./.local/bin/claude` version 2.1.146

### Stabilised findings
1. **`API_KEY_PATH_DUPLICATE_BILLING`** — current bot calls Anthropic API via SDK + `ANTHROPIC_API_KEY`. Operator has Claude Code Pro/Max subscription that includes Claude usage; using a separate API key creates a second billing stream for usage the subscription would cover.
2. **`OAUTH_PATH_OFFICIALLY_SUPPORTED`** — `anthropics/claude-code-action@v1` documents `CLAUDE_CODE_OAUTH_TOKEN` env var as the subscription-auth alternative.
3. **`CLAUDE_CLI_HEADLESS_AVAILABLE`** — `claude -p "prompt" --append-system-prompt "sys"` is the documented headless single-shot pattern.

### Out of scope
- Full migration to `anthropics/claude-code-action@v1` (the agent wrapper). v0 keeps the deterministic Python orchestrator; agent-runtime migration is a future v2 if/when we want Claude to use tools (gh, pytest) during review.
- Multi-model council deliberation. Still waits for Phase D + F.

---

## Tasks

### Task 1: Replace `call_claude` in `tools/pr_review/__main__.py`
Swap `anthropic.Anthropic().messages.create()` for a `subprocess.run(["claude", ...])` call. Update env-var check from `ANTHROPIC_API_KEY` to `CLAUDE_CODE_OAUTH_TOKEN`. Remove the lazy `import anthropic`. `DEFAULT_MODEL` keeps the same string but is now informational (claude CLI picks the model per its own config).

### Task 2: Update `tools/pr_review/cron.py::claude_generate_patch`
Same swap. Same env-var check.

### Task 3: Update both workflows
`.github/workflows/pr-review.yml` and `.github/workflows/council-reviewer-cron.yml`:
- Add a `setup-node@v4` step
- Add `npm install -g @anthropic-ai/claude-code`
- Replace `pip install anthropic` with `pip install` only if other deps are needed (currently none — `gh` and `python` are enough)
- Replace `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}` with `CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`

### Task 4: CHANGELOG
Add Unreleased bullet noting the migration.

### Task 5: Quality gates
```bash
ruff check .
pytest -q orchestrator/tests
python -m tools.pr_review --pr 13 --dry-run   # confirms package still imports
```

### Task 6: PR
Branch `feat/oauth-migration`. Standard template + plan link.

---

## Success Criteria

- `tools/pr_review/__main__.py` no longer imports `anthropic`.
- `tools/pr_review/cron.py` no longer imports `anthropic`.
- Both workflows install `@anthropic-ai/claude-code` and pass `CLAUDE_CODE_OAUTH_TOKEN`.
- `ruff check .` clean; `pytest -q orchestrator/tests` shows 63 passed (Hermes's existing tests pass without modification — they don't test the API call).
- After merge + operator runs `claude` then `/install-github-app`, both bots auth via subscription token; no `ANTHROPIC_API_KEY` ever set.
