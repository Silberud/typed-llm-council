# Contributing

Thanks for the interest. A few conventions:

## Start by reading these three files

If you're new to the codebase, the load-bearing pieces are:

1. **`orchestrator/schemas/verifier_input.py`** — the frozen Pydantic schema that defines what the verifier seat is structurally allowed to receive.
2. **`orchestrator/adapters/base.py`** — the `ContributingAdapter` vs `VerifierAdapter` split that makes Kimi structurally lack an `ask()` method.
3. **`orchestrator/stages/stage3_verification.py`** + **`orchestrator/services/leak_filter.py`** — the protocol layer that takes the decomposer's output, runs the content-channel leak filter, and only then calls Kimi.

Then look at **`orchestrator/tests/test_cove_isolation.py`** + **`orchestrator/tests/test_leak_filter.py`** to see what the design guarantees the project is committed to.

## Where to start

- **Design questions** — open a [Discussion](../../discussions). I'm specifically looking for pushback on the five items in the README's *Looking for feedback on* section.
- **Bug reports** — open an Issue with reproducer steps. Include `python -m orchestrator.supervisor --status` output.
- **Code contributions** — open a PR. Squash-merge by default; no force-pushes to `main`.

## Plan-then-PR workflow (for non-trivial changes)

This repo follows a forensic plan-doc-then-PR convention established in PR #7. For any change beyond a one-line fix:

1. **Open a branch** (e.g. `feat/<short-slug>`, `fix/<short-slug>`, `docs/<short-slug>`).
2. **Write a plan doc** at `docs/plans/YYYY-MM-DD-<short-slug>.md` using [`docs/plans/TEMPLATE.md`](docs/plans/TEMPLATE.md). The plan should include:
   - an audit-loop stabilisation note (the recommendation set stayed unchanged for N consecutive rounds),
   - per-task breakdown with explicit objectives, file changes, and verification commands,
   - success criteria you'll grade yourself against.
3. **Make the changes** in the same branch — the plan doc lands alongside the changes.
4. **Open a PR** that links back to the plan doc and lists which task IDs are addressed.
5. **Quality gates before requesting review:**
   - `ruff check .` clean
   - `pytest -q orchestrator/tests` green
   - the inconsistencies the plan was supposed to fix are actually gone (re-run the audit greps from the plan doc)

The existing entries under `docs/plans/` are examples of the structure — see them for the level of detail expected.

## Council review (manual via slash command)

The maintainer reviews PRs using the [`/council`](docs/reviews/README.md) slash command in Claude Code. It spawns three parallel subagents (Code Reviewer / Security Auditor / Convention Auditor — all Opus 4.7), synthesises their verdicts, and writes a structured review to `docs/reviews/<PR>-iter<K>.md` on this branch.

Reviews are **advisory** — the maintainer confirms each merge. The slash command runs entirely inside the maintainer's local Claude Code session; there is no CI bot, no API key, no GitHub Actions secret. Expect a review file per invocation (iter1, iter2, …) capturing how subsequent commits shifted the verdict.

If a review surfaces a substantive concern, address it in a follow-up commit or argue back in a PR comment — the next `/council` invocation will read both the new diff and the comment thread.

## Tests

The default suite runs cleanly without credentials:

```bash
pytest orchestrator/tests/
```

This is what CI runs. Keep it green.

**Do not run `orchestrator/tests/_live/` in CI or in your PR.** It calls real
Claude + real Kimi — it burns your subscription quota and won't authenticate
in CI without your secrets. Use it locally to verify Phase E changes before
opening a PR. The default `pytest` invocation excludes it via
`norecursedirs` in `pyproject.toml`.

## Code style

`ruff check .` should pass. Type hints are not enforced project-wide but the
public schemas (`orchestrator/schemas/`) and adapter base classes
(`orchestrator/adapters/base.py`) are type-strict — please don't loosen them.

## The load-bearing invariants

`orchestrator/tests/test_cove_isolation.py` is **the locked CI safety net**
for invariants #2 (Verifier is non-voting) and #7 (no member sees another
member's reasoning before Stage 4). If a PR weakens type-level enforcement,
substring-leak detection, or property-based fuzzing in that file, it must
either pass the existing tests or include a documented spec-level reason
in the PR description.

## Building deferred phases

Phases C, D, F, G, H are in the roadmap. If you want to claim one:

1. Open a Discussion first describing your approach.
2. Stick to the spec at `docs/internal_spec_v2.2.md` — deviations are fine
   if justified, but document them in `docs/operator_setup.md` (or a new
   gaps file you create) and reference them in the PR.
3. Each phase has acceptance criteria in spec §11 — your PR should explain
   how it meets them.
