# Slash-Command Pivot Implementation Plan

> **Status:** Plan locked after recognising the prior CI-based architecture was the wrong shape.

**Goal:** Replace the entire CI-based PR review apparatus (PRs #15, #19, #20) with a single Claude Code slash command (`.claude/commands/review-pr.md`) that uses the native Agent tool to spawn parallel subagents.

**Why the pivot:** The CI approach kept hitting friction:
- v0 needed a token (ANTHROPIC_API_KEY) → operator setup cost.
- OAuth migration (v1) introduced more setup (`claude setup-token`) and `claude -p` in fresh CI runners rejected the long-lived OAuth token with `401 Invalid bearer token` because the CLI's OAuth-exchange step requires keychain state that CI doesn't have.
- The fundamental insight: the operator already runs `claude` interactively in the authenticated session. Spawning subagents via the Agent tool from inside that session needs **no new auth at all**. CI was the wrong layer.

**Architecture:** Project-level slash command at `.claude/commands/review-pr.md`. Invoked as `/review-pr <N>`. **Spawns three parallel external-CLI calls — one per LLM vendor — via the Bash tool.** Members:

- **GPT-5.5 (Architect)** via `codex exec` (ChatGPT Pro subscription auth)
- **Gemini 3.1 Pro (Researcher)** via `gemini -p` (OAuth auth, no API key)
- **Qwen 3.6 (Analyst)** via local Ollama HTTP (`qwen3.6:35b-a3b-coding-nvfp4`)

The chairman (Claude — the operator's own `claude` session) synthesizes the three vendors' verdicts. This realises the council's anti-single-vendor-bias claim that the README has made since v2.3.0 — three different vendors voting, one chairman synthesizing.

**Deferred to v1 of the slash command:**
- Stage 2 D3 advocate/juror role rotation
- Stage 3 CoVe verification by Kimi (non-voting verifier seat)
- Stage 4 AceMAD peer-prediction weighted aggregation
- Stage 6 FOCUS drift escalation
- Grok (Skeptic) seat — still stubbed (CG-001, no OAuth path)

---

## What's removed

- `.github/workflows/pr-review.yml`
- `.github/workflows/council-reviewer-cron.yml`
- `tools/pr_review/{__main__,prompts,actions,cron}.py`
- `tools/__init__.py`
- `orchestrator/tests/test_pr_review_bot.py`

## What's added

- `.claude/commands/review-pr.md` — the slash command (single file, ~9 kB)
- This plan doc

## What's updated

- `CHANGELOG.md` — Unreleased entry noting the pivot
- `docs/reviews/README.md` — explains the new flow
- `CONTRIBUTING.md` — points contributors at `/review-pr` instead of the bot

## What's kept (historical record)

- `docs/plans/2026-05-27-pr-review-bot.md`
- `docs/plans/2026-05-27-reviewer-cron.md`
- `docs/plans/2026-05-27-oauth-migration.md`
- `docs/reviews/13-iter1.md` (manually-written calibration review)

These remain as a record of the path walked. The current plan deliberately reverses the architectural decisions in those plans.

---

## Success criteria

- `.claude/commands/review-pr.md` exists; YAML frontmatter parses.
- All CI workflow files / Python module files for the old bot are removed.
- `pytest -q orchestrator/tests` shows green (the test that depended on the removed module is also removed, so the count drops).
- After this PR merges: in a fresh Claude Code session in this repo, typing `/review-pr` appears in autocomplete; typing `/review-pr 23` runs the full council protocol and writes `docs/reviews/23-iter1.md`.
- No new secrets need to be set on the repo (operator can revoke `CLAUDE_CODE_OAUTH_TOKEN` if desired).

## Open question for follow-up

Whether to wire local automation (e.g. a launchd job that runs `claude -p "/review-pr X"` headlessly every 6h) is a separate decision. The slash command works fine purely manually; automation is an opt-in extension. If pursued, it would need to live in a separate plan because headless `claude -p` interaction with custom slash commands needs its own validation.
