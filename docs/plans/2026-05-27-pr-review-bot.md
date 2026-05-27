# PR Review Bot (v0) Implementation Plan

> **⚠️ DEPRECATED — historical record only.** This plan was implemented as PR #15 but the resulting CI-based bot was later **removed** in PR #27 in favour of a Claude Code slash command (`.claude/commands/review-pr.md`). See [`2026-05-27-slash-command-pivot.md`](2026-05-27-slash-command-pivot.md) for the architecture that replaced it. The Python bot and its GitHub Actions workflow no longer exist in the repo.


> **Status:** Plan stabilised after 3 consecutive zero-finding rounds (R6, R7, R8) with perspectives spanning security/PI defense, failure modes, fork safety, and convention fit.

**Goal:** A GitHub-Actions reviewer bot that runs on every PR to this repo. Reads the PR diff + body, produces a structured forensic review via a single LLM call (Claude), commits the review as a file to the PR branch, and posts a comment with the link.

**Architecture:** Pure GitHub Actions workflow + a small Python orchestrator. No third-party wrapper Actions, no multi-model deliberation yet (v1 territory), no telemetry DB (v1 territory). The cron uses the repo's *output convention* (`docs/reviews/`) rather than any of the framework's internal stages — that's deliberate. v0 ships a single-LLM critique with the same forensic protocol we ran manually on PR #12. v1 swaps the single LLM for the full multi-stage council once Phases D + F land.

**Tech stack:** GitHub Actions, Python 3.12, Anthropic SDK (`anthropic` PyPI package), `gh` CLI for GitHub API interactions, markdown for output.

---

## Audit Evidence

### Repository state verified before planning
- Latest origin/main: `38f256e` (PR #12 squash merge: "docs: tighten public credibility follow-up").
- `pytest -q orchestrator/tests` → `55 passed`.
- `ruff check .` → `All checks passed!`.
- Latest GH Actions on `38f256e` → green (Python 3.11 + 3.12 pytest).
- v2.3.0 tag published.

### Stabilised audit findings
1. **`PR_REVIEW_BOT_MISSING`** — Every PR (Hermes, Dependabot, future contributors) currently relies on Igor reading the PR and either invoking me interactively or merging blind. There's no persistent, public, structured artefact of the review.
2. **`PI_DEFENSE_ABSENT`** — Any future PR-review automation will be exposed to prompt-injection through PR titles, bodies, and code comments. No sanitization currently exists.
3. **`NO_REVIEW_CORPUS`** — Phase H bootstrap data will need labelled deliberation sessions. Without an artefact-emitting reviewer, the corpus is empty.

### What is NOT in scope (deferred to v1+)
- Multi-model deliberation (waits for Phase D + Phase F to ship; v1).
- Cross-iteration concern tracking — comparing iter K against iter K-1 (waits until we have data; v1).
- SQLite WAL telemetry (waits for Phase H; v1).
- Sandboxed execution beyond GitHub Actions runner defaults (v2).
- Auto-merge authority (v2+; for now bot never merges).
- Council members other than Claude (v1; the repo already has the adapters, just not wired into the cron).

---

## Task 1: Reviewer orchestrator (`tools/pr_review/`)

**Objective:** A Python package that, given a PR number, reads the PR, produces a forensic review, and writes the artefact.

**Files:**
- Add: `tools/pr_review/__init__.py`
- Add: `tools/pr_review/__main__.py` — entrypoint (`python -m tools.pr_review --pr N`)
- Add: `tools/pr_review/prompts.py` — system + user prompt builders, PI defense delimiters
- Add: `tools/__init__.py` (if not already there)

**Behaviour:**
- Reads PR metadata + diff via `gh api` (subprocess; no extra Python deps)
- Truncates diff to ≤ 50K characters; notes truncation if applied
- Runs a regex pre-scan for prompt-injection patterns; collects hits as a structured `pi_flags` list
- Wraps PR title/body/diff in `<UNTRUSTED_PR_CONTENT>` delimiters before sending to Claude
- Calls Claude (Opus 4.7) once with a structured system prompt
- Counts existing review files for this PR to determine iteration `K`
- Writes `docs/reviews/<PR>-iter<K>.md` containing: triage table, PI scan result, per-claim verdict table, council-style decision section
- Returns the path on stdout

**Verification:**
```bash
python3 -m tools.pr_review --pr 12 --dry-run
```
Expected: prints the path it *would* write, doesn't actually call the API or write the file.

---

## Task 2: GitHub Actions workflow

**Objective:** Trigger the reviewer on every PR open/synchronize/reopen, commit the artefact to the PR branch, post a comment.

**Files:**
- Add: `.github/workflows/pr-review.yml`

**Configuration:**
- Trigger: `pull_request: [opened, synchronize, reopened]`
- Concurrency: per-PR, cancel-in-progress (re-pushing supersedes prior review run)
- Permissions: `contents: write` + `pull-requests: write` only
- Secret: `ANTHROPIC_API_KEY`
- Skips on forks (no secret access — GH default, correct)

**Steps:**
1. Checkout PR head SHA
2. Set up Python 3.12
3. Install `anthropic` (only dependency beyond stdlib)
4. Run `python -m tools.pr_review --pr ${{ github.event.pull_request.number }}`
5. Commit the new review file back to the PR branch with a `[skip ci]` message to avoid recursive triggers
6. Post a PR comment linking to the file

**Verification:** After merge, opening any PR (or pushing to one) should trigger the workflow visible at `gh run list --workflow=pr-review.yml`.

---

## Task 3: `docs/reviews/README.md`

**Objective:** Explain the convention to any reader who finds the directory.

**Files:**
- Add: `docs/reviews/README.md`

**Content:** What this directory holds, file naming (`<PR>-iter<K>.md`), how it's generated, that it is NOT a merge gate (advisory only), what the schema looks like.

---

## Task 4: CONTRIBUTING update

**Objective:** Set contributor expectations.

**Files:**
- Modify: `CONTRIBUTING.md`

**Change:** One paragraph under a new "Automated review" heading: PRs trigger an automated forensic review; the review is advisory, committed to your branch as `docs/reviews/<PR>-iter<K>.md`. The maintainer remains the merge gate.

---

## Task 5: CHANGELOG Unreleased

**Files:**
- Modify: `CHANGELOG.md`

**Change:** Add bullet under `## Unreleased`:
- `Tools: PR review bot (v0) — every PR triggers a structured forensic review, committed to the PR branch as docs/reviews/<N>-iter<K>.md.`

---

## Task 6: Quality gates

**Commands:**
```bash
ruff check .
pytest -q orchestrator/tests
python3 -m tools.pr_review --pr 12 --dry-run   # verify the package imports and the dry-run path
```
Expected: all green.

---

## Task 7: Commit + push + PR

**Branch:** `feat/pr-review-bot`

**Commands:**
```bash
git add tools/ .github/workflows/pr-review.yml docs/reviews/README.md \
        CONTRIBUTING.md CHANGELOG.md docs/plans/2026-05-27-pr-review-bot.md
git commit -m "feat: PR review bot (v0) — forensic single-LLM review on every PR"
git push -u origin feat/pr-review-bot
gh pr create --title "..." --body "..."
```

---

## Task 8: After merge — add `ANTHROPIC_API_KEY` secret + retroactive validation

After the PR merges, the maintainer must:
1. `gh secret set ANTHROPIC_API_KEY` (one-time)
2. Run `python3 -m tools.pr_review --pr 12` locally to produce a retroactive review of PR #12; compare against the manual critique to validate prompt quality
3. Optionally: produce retroactive reviews for PRs #7, #8, #9 to backfill `docs/reviews/`

---

## Success Criteria

- `tools/pr_review/` exists and is importable; `python -m tools.pr_review --pr N --dry-run` works.
- `.github/workflows/pr-review.yml` exists, syntactically valid (gh actions parses without error).
- `docs/reviews/README.md` exists.
- `CONTRIBUTING.md` documents the bot.
- `CHANGELOG.md` Unreleased has the new bullet.
- `ruff check .` passes; `pytest -q orchestrator/tests` 55 passed.
- PR opened and CI green.
- Post-merge: `ANTHROPIC_API_KEY` set; retroactive PR #12 review produced and inspected.
