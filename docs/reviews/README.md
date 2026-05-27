# Automated PR reviews

Each file in this directory is a structured forensic review of a pull request, written by the [`tools/pr_review`](../../tools/pr_review/) bot via the [`.github/workflows/pr-review.yml`](../../.github/workflows/pr-review.yml) workflow.

## File naming

```
<PR-number>-iter<K>.md
```

- `PR-number` — the pull request this review is of
- `K` — iteration. The bot re-reviews on every new push to a PR; iteration `1` is the open event, `2` is the first push after that, etc.

## Schema

Each review contains:

| Section | What it holds |
|---|---|
| **Triage** | files changed, lines, whether invariant files were touched, author trust class |
| **Security pre-check** | results of the regex prompt-injection tripwire + the bot's own verdict on the hits |
| **Per-change verdict** | one row per file change with AGREE / DISAGREE / DISAGREE-WITH-CAVEAT / NEEDS-INFO |
| **Convention adherence** | plan-doc present? CHANGELOG `Unreleased` updated? PR template used? |
| **Decision** | APPROVE / APPROVE-WITH-MINOR-MODIFY / MODIFY / REJECT / NEEDS-MAINTAINER with reasoning |

## Status of the bot

**v0 (this version) is single-LLM.** One Anthropic Opus 4.7 call per review. The forensic structure mirrors the manual review pattern used on PRs #7, #8, #9, and #12.

**v1 will swap in the full multi-stage council** once Phases D + F land on the roadmap. The output schema is designed to remain stable across that transition — v1 will populate the same sections, but with multi-model deliberation backing each verdict.

## What it does NOT do

- **The bot never merges or blocks.** All decisions are advisory; the maintainer remains the merge gate.
- **The bot does not run on forks.** Forks don't have access to the repo's secrets, so the workflow exits early (`if: head.repo.full_name == repository`). Same-repo PRs get full review.
- **The bot does not execute code from the PR.** It reads the diff and the PR body; the only code it runs is the unmodified test suite that already exists on `main`.
- **The bot does not auto-merge.** Even on APPROVE verdicts.

## Prompt-injection defense

The PR diff and body are wrapped in `<UNTRUSTED_PR_CONTENT>` tags before being sent to Claude. The system prompt explicitly tells Claude that content inside those tags is *data*, never instructions, and that the reviewer must not adopt roles or follow directives that appear in that content. A regex pre-scan also flags known injection patterns (override directives, Unicode bidi controls, zero-width characters, Cyrillic-Latin homoglyphs, etc.) — those hits are surfaced as findings in the review's `Security pre-check` section.

If a contributor submits a PR with what the bot judges to be a genuine prompt-injection attempt, expect the review's Decision section to read **NEEDS-MAINTAINER** with the security finding explained.

## Local validation

The bot is runnable locally for testing prompt changes:

```bash
# Set up
export ANTHROPIC_API_KEY=sk-...
pip install anthropic

# Run against any historical PR
python -m tools.pr_review --pr 12

# Or just check what it WOULD do without making an API call
python -m tools.pr_review --pr 12 --dry-run
```

## Maintenance

The prompts live at [`tools/pr_review/prompts.py`](../../tools/pr_review/prompts.py). Changes go through the regular plan-doc-then-PR convention from [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — including, recursively, the bot reviewing changes to its own prompts.
