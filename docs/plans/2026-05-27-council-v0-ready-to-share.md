# Council v0 — Ready-to-Share Polish Plan

> **Status:** Plan stabilised after 3 consecutive zero-finding rounds across outside-contributor, academic, reproducibility, security/auditor, UX/discoverability, dogfooding, and cleanup-hygiene perspectives.

**Goal:** Bring the typed-llm-council repo from "shipped + works" to "professionally shareable" — surface the working `/review-pr` slash command as the primary value proposition, document prerequisites cleanly, demonstrate the first real council run, and clean up the deprecated CI bot's trail.

**Architecture:** No code changes to the orchestrator. Slash-command tweak (`timeout` portability fix), README facelift, new Council Quickstart doc, deprecation banners on stale plan docs, CHANGELOG note with link to first real review artefact.

**Tech stack:** Markdown only.

---

## Audit Evidence

### Repository state verified before planning
- Latest origin/main: `3379479 review(council v0): MODIFY verdict on PR #24`
- Slash command `.claude/commands/review-pr.md` (multi-provider) lives on main
- First real artefact at `docs/reviews/24-iter1.md` (3/3 MODIFY HIGH on Hermes's #24)
- Tests: 60/60 passing (Python 3.11/3.12/3.13)

### Stabilised findings
1. **`SLASH_CMD_MACOS_PORTABILITY`** — `.claude/commands/review-pr.md` uses bare `timeout` which isn't on macOS without `coreutils`. The first real run hit this and had to drop the timeout.
2. **`HERMES_STATUS_MISSING_RECENT_PASSES`** — `docs/hermes_findings_status.md:73` shows test counts up to Pass 2 (55/55) but not the subsequent hardening pass (63/63) or slash-command pivot (60/60).
3. **`README_NO_TRY_IT_NOW`** — Outside contributor lands on README and learns about phases A/B/E but doesn't immediately discover that `/review-pr` is the working artefact they can run today.
4. **`NO_COUNCIL_QUICKSTART`** — Prerequisites for running `/review-pr` (codex/gemini/ollama+qwen) are scattered; no single onboarding doc.
5. **`STALE_PLAN_DOCS`** — `2026-05-27-{pr-review-bot,reviewer-cron,oauth-migration}.md` document architectures that no longer exist. Without deprecation banners, visitors might follow obsolete instructions.

### Out of scope (v1+)
- Automation of `/review-pr` invocation (e.g. launchd job watching for new PRs).
- Adding a `--dry-run` mode to the slash command.
- Adding a `--members` flag to choose which vendors participate.
- Cutting v2.4.0 release (the polish here lands under Unreleased; tag-cut is separate).
- Closing stale PRs #23/#26 (operator decision; this plan only proposes).

---

## Tasks

1. **Slash command portability** — replace bare `timeout 120 …` with `${TIMEOUT_BIN:-} ${TIMEOUT_BIN:+120} …` so it gracefully degrades when `timeout` isn't installed (default on macOS) and is opt-in via `export TIMEOUT_BIN=timeout`.
2. **Hermes status trail** — add the two missing test-total entries (post-hardening 63/63, post-pivot 60/60) to `docs/hermes_findings_status.md:73`.
3. **README facelift** — add "Try it now — `/review-pr` slash command" section near the top, surface the multi-vendor design, link `docs/reviews/24-iter1.md` as evidence.
4. **`docs/council_quickstart.md`** — comprehensive onboarding doc: prereqs table, install commands, auth methods, run instructions, anti-bias explanation, cost note, v0 limitations.
5. **Deprecation banners** — header on `2026-05-27-{pr-review-bot,reviewer-cron,oauth-migration}.md` pointing at the slash-command pivot.
6. **CHANGELOG** — enrich the slash-command pivot entry with link to the first real review artefact (PR #24 verdict).

## Quality gates

- `ruff check .` clean.
- `pytest -q orchestrator/tests` shows 60 passed.
- YAML frontmatter on `.claude/commands/review-pr.md` parses.
- Grep verifies no remaining bare `timeout` in the slash command.

## Success criteria

- An outside contributor reading the README in <60 seconds understands that `/review-pr` is the working artefact and `docs/reviews/24-iter1.md` is real evidence.
- The Council Quickstart doc gets someone from "freshly cloned repo" to "first review artefact" in <5 minutes (assuming the prerequisite CLIs are already authenticated).
- Deprecated plan docs no longer mislead — banners make it obvious they're historical.

## Post-merge actions (operator decisions, not blocking)

- Close stale PRs #23 (`security: gate reviewer cron auto-merge`) and #26 (`security: redact Claude token diagnostics`) — both reference the deleted CI bot infrastructure.
- Post Discussion #1 comment announcing the multi-provider council with link to `docs/reviews/24-iter1.md`.
- Consider cutting v2.4.0 once a few real `/review-pr` runs have accumulated in `docs/reviews/`.
