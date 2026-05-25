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
