# Reviewer Cron (v1) Implementation Plan

> **Status:** Plan stabilised after 3 consecutive zero-finding rounds.

**Goal:** Add a 6-hourly scheduled GitHub Action that iterates every open PR, runs the v0 per-PR reviewer (already shipped in PR #15), parses the verdict, and **acts** on it: auto-merge on APPROVE, fix-up commit on MODIFY, comment+label on REJECT/NEEDS-MAINTAINER. Pairs with Hermes's own 15-minute opener cron (operator-managed on the Hermes Claude Code instance).

**Architecture:** Single scheduled workflow → Python entrypoint → iterates open PRs → per PR: re-runs reviewer if no current iteration → parses verdict → dispatches to action handler. No new external deps beyond `anthropic` (already a v0 dep).

---

## Audit Evidence

### Repository state verified before planning
- `git log --oneline -1` → `9868266 test: harden release packaging and demo guarantees (#13)`
- `pytest -q orchestrator/tests` → 60 passed
- `ruff check .` → All checks passed!
- v0 per-PR reviewer (PR #15) live; pending operator setting `ANTHROPIC_API_KEY` secret.

### Stabilised findings
1. **`PER_PR_BOT_INSUFFICIENT_AS_META_LOOP`** — v0 bot reviews per push but never acts. Hermes opens PRs every 15 min; without an actor, queue grows.
2. **`NO_MODIFY_AUTOMATION`** — Igor's plan-loop calls for fix-up commits when MODIFY verdict appears; no machinery for that yet.
3. **`NO_VERDICT_PARSER`** — v0 writes markdown reviews; no programmatic verdict extraction.

### Out of scope (v2+)
- Multi-model council deliberation in the cron itself (waits for Phase D + F).
- DRIFTPolicy / FOCUS iteration cap on the same PR (waits for Phase G).
- SQLite WAL telemetry (waits for Phase H).
- Auto-close on REJECT (kept manual — operator decision per PR).

---

## Task 1: Verdict parser

Add `--verdict-only` flag to `tools.pr_review.__main__`. Reads the latest existing review file for `--pr N` (does NOT call the API), extracts the **Decision** section's bold verdict token (`APPROVE` / `APPROVE-WITH-MINOR-MODIFY` / `MODIFY` / `REJECT` / `NEEDS-MAINTAINER`), prints it on stdout.

If no review file exists, exits 0 with stdout empty (caller knows to run the full review first).

## Task 2: `tools/pr_review/actions.py`

Three pure functions, each wrapping `gh` CLI / `git` commands:
- `merge_pr(n: int) -> bool`
- `push_fixup(n: int, head_ref: str, patch_text: str) -> bool` — writes patch to a temp file, `git apply`, commit `[skip ci]`, push
- `comment_and_label(n: int, body: str, label: str) -> None`

Each returns success boolean so the cron can decide whether to fall through.

## Task 3: `tools/pr_review/cron.py`

Top-level:
```python
def main():
    open_prs = list_open_prs()
    for pr in open_prs:
        if not has_current_iter(pr):
            run_review(pr)  # produces docs/reviews/<n>-iter<k>.md
        verdict = parse_verdict(pr)
        dispatch(pr, verdict)
```

Dispatch table:
| Verdict | Action |
|---|---|
| `APPROVE` | `merge_pr(n)` |
| `APPROVE-WITH-MINOR-MODIFY` | `comment_and_label(n, "soft suggestions noted; merging on green CI", "auto-mergeable")` then `merge_pr(n)` |
| `MODIFY` | Ask Claude for unified-diff patch addressing the review's Required Actions section. `push_fixup` if patch is non-empty and applies cleanly; else `comment_and_label(..., "needs-modify")` |
| `REJECT` | `comment_and_label(n, "<review excerpt>", "needs-maintainer")` |
| `NEEDS-MAINTAINER` | `comment_and_label(n, "<review excerpt>", "needs-maintainer")` |
| `<empty>` / parse error | No-op, log warning |

Each PR is processed in a try/except so one bad PR doesn't block the rest.

## Task 4: Workflow `.github/workflows/council-reviewer-cron.yml`

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # every 6 hours
  workflow_dispatch:        # manual button
permissions:
  contents: write
  pull-requests: write
```

One job: checkout main, install `anthropic`, run `python -m tools.pr_review.cron`. Same key handling as v0 — gracefully no-ops if `ANTHROPIC_API_KEY` is unset.

## Task 5: CHANGELOG Unreleased

Add bullet:
- `Tools: reviewer cron (v1) — every 6h iterates open PRs, runs forensic review (re-using v0), and acts: auto-merge on APPROVE, fix-up commit on MODIFY (Claude-generated patch), comment+label otherwise.`

## Task 6: Quality gates

```bash
ruff check .
pytest -q orchestrator/tests
python -m tools.pr_review.cron --dry-run   # lists open PRs, prints intended actions, no side effects
```

## Task 7: PR

Branch `feat/reviewer-cron`. Standard template; plan doc linked.

---

## Success Criteria

- Workflow YAML parses; `schedule` and `workflow_dispatch` triggers visible in `gh workflow list`.
- `python -m tools.pr_review.cron --dry-run` enumerates open PRs and prints `<pr> <verdict> <action>` per line.
- Dispatch covers all 6 verdict states; unknown verdict no-ops with a warning, never crashes the run.
- `git apply` failure on MODIFY falls back to comment-only — never partially-applied patches.
- All commits made by the cron carry `[skip ci]` to prevent recursion with the v0 per-PR workflow.
