# Reviewer cron safety gates — forensic stabilization plan

Date: 2026-05-27

## Context

Hermes recurring audit reviewed `main` at `f922190` after PR #19 added the
scheduled reviewer cron. The cron gives LLM review verdicts repository-write
effects: merge on `APPROVE`, generated fix-up commits on `MODIFY`, and labels /
comments on blocking verdicts.

## Stabilized plan loop

Machine-checkable predicates were evaluated across implementation, tests, docs,
changelog, workflows, public claims, and PR-review dataflow.

- `PLAN-20260527-CRON-GATE-1`: Skeptic/security/adversarial dataflow review found that `APPROVE` led directly to `gh pr merge` without checking PR CI state.
- `PLAN-20260527-CRON-GATE-2`: Architect/maintainer/release-manager review found docs still said the bot does not auto-merge, contradicting the new cron surface.
- `PLAN-20260527-CRON-GATE-3`: First-time-contributor/release review found truncated diffs were annotated but not structurally fail-closed before a verdict could trigger cron actions.

The same three required findings were stable for three consecutive loops; no
additional patchable release-blocking finding displaced them.

## Implementation

1. Add a `pr_checks_green()` gate before reviewer-cron auto-merge. It fails closed on absent checks, pending/failing checks, invalid JSON, or `gh` failure.
2. Require `NEEDS-MAINTAINER` in the reviewer system prompt when the PR diff is truncated, and machine-enforce that verdict before writing the review artefact.
3. Update `docs/reviews/README.md` so the public safety model distinguishes the advisory per-PR bot from the scheduled actor cron.
4. Add regression tests for the merge gate, truncated-diff prompt invariant, and truncated-diff verdict override.

## Verification targets

- `ruff check .`
- `pytest -q orchestrator/tests`
- `python examples/stage3_verification_demo.py`
- Secret/dangerous-addition scans over the patch
- Three execution-audit loops with stable zero required changes
