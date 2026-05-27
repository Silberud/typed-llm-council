<!--
Per CONTRIBUTING.md, non-trivial changes follow a plan-doc-then-PR convention.
For one-line fixes (typos, comment grammar), you can delete this template body
and write a 2-sentence description.
-->

## Summary

<!-- 2–3 sentences. What changes, and why. -->

**Plan doc:** `docs/plans/YYYY-MM-DD-<short-slug>.md`
<!-- Link the plan doc that landed in (or with) this PR. -->

## Tasks addressed

<!-- Reference the plan doc's task IDs and tick them off. -->

- [ ] Task 1 — …
- [ ] Task 2 — …

## Quality gates

- [ ] `ruff check .` passes
- [ ] `pytest -q orchestrator/tests` shows N passed
- [ ] Plan-doc audit greps re-run; the inconsistencies the plan was supposed to fix are gone
- [ ] `examples/stage3_verification_demo.py` exits 0 (if relevant)
- [ ] No new secrets, plaintext keys, or `.env`-style files committed

## Out of scope (deliberately deferred)

<!-- Anything you considered and chose not to land in this PR, with a one-line "why deferred". -->

- …

## Type of change

<!-- Pick one. -->

- [ ] Documentation only
- [ ] Bugfix
- [ ] New feature
- [ ] Tooling / DX / CI
- [ ] Phase implementation (link tracking issue #N)
