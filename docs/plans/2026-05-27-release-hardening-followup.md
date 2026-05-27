# Release-Hardening Follow-up Implementation Plan

> **Status:** Plan audit-loop stabilised after three consecutive no-change rounds (rounds 4, 5, 6). Earlier rounds added packaging, trust-boundary regression, release-manager, CI/tooling, first-time-contributor, and stale-doc perspectives.

**Goal:** Convert the current post-v2.3.0 forensic review into a focused hardening PR that improves release/install reliability, protects public no-real-model-call claims with tests, and aligns contributor-facing docs/config with the current implementation.

**Architecture:** Small code/test/docs/tooling change. No product behaviour change except packaging the default `orchestrator/config.toml` into wheels and expanding CI coverage.

**Tech Stack:** Python packaging, pytest, GitHub Actions, Dependabot, Markdown/TOML/YAML.

---

## Audit Evidence

### Repository state verified before planning

- Latest origin/main: `38f256e` (`docs: tighten public credibility follow-up (#12)`).
- Repo public; Discussions enabled; no open PRs at planning time.
- Latest main CI on `38f256e` green.
- Local gates before patch: `ruff check .` passed; `pytest -q orchestrator/tests` showed 55 passed; `examples/stage3_verification_demo.py` exited 0 and reported `placeholder_confidence_threshold`.

### Plan-loop history

1. **Round 1 — baseline public credibility scan:** found no live private-staging residue after PR #12, but identified packaging/install and test-hardening candidates.
2. **Round 2 — packaging/release-manager perspective:** added `PKG_CONFIG_TOML_MISSING` after wheel inspection showed `orchestrator/config.toml` was absent from built wheels.
3. **Round 3 — adversarial trust-boundary perspective:** added demo regression test and comparator config parsing tests so PR #12's safety guarantee is executable, not just prose.
4. **Round 4 — maintainer/tooling perspective:** added Python 3.13 CI and pre-commit Dependabot coverage; no removals.
5. **Round 5 — first-time contributor/docs perspective:** added stale `KNOWN_GAPS.md` config reference and leak-filter docstring alignment; no new categories.
6. **Round 6 — skeptical no-spam pass:** rejected broad ruff-format/pre-commit-in-CI as too noisy for this PR; stable finding set unchanged for the third consecutive round.

### Stabilised findings

1. **`PKG_CONFIG_TOML_MISSING`** — built wheels omit `orchestrator/config.toml`, although `supervisor.py` expects it as the default config path.
2. **`DEMO_NO_REAL_CALLS_UNTESTED`** — the Stage 3 demo now forces placeholder comparator, but no regression test proves local `comparator_mode = "real"` cannot trigger a real comparator path.
3. **`COMPARATOR_CONFIG_PARSE_UNTESTED`** — dispatch tests mock `_comparator_mode_from_config`; they do not test actual config-shape parsing/fallback semantics.
4. **`PY313_NOT_IN_CI`** — package metadata says `>=3.11`; local 3.13 passes, but CI only covers 3.11/3.12.
5. **`PRECOMMIT_PINS_NOT_UPDATED`** — `.pre-commit-config.yaml` pins hook repos, but Dependabot does not cover the `pre-commit` ecosystem.
6. **`GROK_CONFIG_DANGLING_DOC_REF`** — `orchestrator/config.toml` points to nonexistent `KNOWN_GAPS.md` instead of existing `docs/operator_setup.md` CG-001.
7. **`LEAK_FILTER_DOCSTRING_OVERBROAD`** — module-level leak-filter docstring still describes single-word role markers and operator-prompt role checks broader than the implementation actually enforces.

### Deliberately out of scope

- Running `pre-commit run --all-files` in CI: current ruff-format hook reformats many existing files. That should be a separate formatting PR, not mixed with release hardening.
- Removing `council-replay`: potentially valid surface cleanup, but it changes advertised console scripts and needs maintainer intent.
- Cutting v2.3.1: this PR records changes under `Unreleased`; release cutting remains separate.

---

## Tasks

1. Include `orchestrator/config.toml` as setuptools package data and add a wheel-inspection regression test.
2. Add config parsing tests for `_comparator_mode_from_config`.
3. Add a Stage 3 demo regression test proving `comparator_mode = "real"` cannot bypass the forced placeholder comparator.
4. Add Python 3.13 to CI.
5. Add Dependabot coverage for pre-commit hooks.
6. Align `orchestrator/config.toml` Grok-stub comment with existing docs.
7. Narrow the leak-filter module docstring to match current implementation.
8. Update CHANGELOG Unreleased.
9. Run quality gates and execution-audit loops until stable.

---

## Success Criteria

- `ruff check .` passes.
- `pytest -q orchestrator/tests` passes with new tests included.
- `python examples/stage3_verification_demo.py` exits 0 and reports `placeholder_confidence_threshold`.
- A built wheel contains `orchestrator/config.toml`.
- PR CI passes on Python 3.11, 3.12, and 3.13.
