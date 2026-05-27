# Council Review — PR #13, Iteration 1

**Title:** test: harden release packaging and demo guarantees
**Author:** Andrjushapa (Hermes Agent / GPT-5.5)
**Submitted (HEAD SHA):** (PR #13 head)
**Profile:** forensic
**Reviewer:** Claude Opus 4.7 — manual, written using the bot's v0 schema. (Automated bot review was not produced because `ANTHROPIC_API_KEY` was not yet set as a repo secret when this PR was opened.)

## T — Triage

| Feature | Value |
|---|---|
| Files changed | 11 |
| Lines | +220 / -13 |
| Touches invariant files | yes — `services/leak_filter.py` (docstring only) + `tests/test_cove_isolation.py` (Hypothesis `assume()`) |
| Author trust | known-collaborator (Hermes Agent — co-developing this repo) |
| CI status pre-review | green on Python 3.11 + 3.12 + 3.13 |

## S — Security pre-check

### Tripwire scan
- pi_flags: none. PR body uses forensic-review style; no injection patterns.

### Verdict
**SECURITY-CLEAR.** No suspicious code, no Unicode tricks, no role-reassignment patterns. The only file behaviour the PR changes is the wheel manifest (adds `orchestrator/config.toml` to package data) and the test surface (adds 6 tests). The leak-filter docstring change is purely textual.

## Per-change verdict

| File | Change | Verdict | Reasoning |
|---|---|---|---|
| `pyproject.toml` | Add `orchestrator/config.toml` to package-data; add `build>=1.2` dev dep | AGREE | Without package-data, wheel installs break `supervisor.py` default config path. `build` is needed for the regression test. |
| `orchestrator/config.toml` | Replace dangling `KNOWN_GAPS.md` reference with `docs/operator_setup.md → CG-001` | AGREE | `KNOWN_GAPS.md` doesn't exist in the public repo. Honest correction. |
| `orchestrator/services/leak_filter.py` | Narrow module docstring to match impl (multi-word ROLE_MARKERS, no operator-prompt-role-check) | AGREE | Old docstring overstated what `check_inputs_clean` actually catches. New docstring is descriptive, not aspirational. |
| `orchestrator/tests/test_cove_isolation.py` | Add Hypothesis `assume()` to skip false-positive overlap cases | AGREE | Hypothesis hygiene. The skipped cases exercise the fail-closed tampering path (already covered by other tests), not the Kimi-prompt isolation invariant this property targets. Doesn't weaken the test. |
| `orchestrator/tests/test_config_and_packaging.py` (NEW) | 4 tests: comparator mode real/placeholder/fallback + wheel-inspection | AGREE | Each test is mechanically verifiable. The wheel-inspection test builds a real wheel and reads the manifest — direct, unmockable. |
| `orchestrator/tests/test_stage3_demo.py` (NEW) | Regression test: `comparator_mode = "real"` in config cannot bypass the demo's forced placeholder | AGREE — **exemplary** | This is the test PR #12's defensive fix needed. Sets the dangerous config explicitly, mocks the dangerous function to raise if called, asserts safe behaviour still occurs. Worth emulating elsewhere in the suite. |
| `.github/workflows/ci.yml` | Add Python 3.13 to matrix | AGREE | I had this on my deferred list; Hermes shipped it with CI proof. |
| `.github/dependabot.yml` | Add `pre-commit` package-ecosystem | AGREE | Closes the soft pushback in PR #12 ("or add Dependabot's pre-commit ecosystem if desired"). |
| `README.md` | (1) Soften "everything is local" to scope-correct wording. (2) Update `test_leak_filter.py` count `12 → 16`. (3) Update overall `55/55 → 60/60` with breakdown. | AGREE | All three are factual corrections. The "everything is local" softening is the most substantive — old wording was false the moment a user enables live model calls. |
| `CHANGELOG.md` | Add 6 bullets under Unreleased | AGREE | All bullets accurately describe what landed. |
| `docs/plans/2026-05-27-release-hardening-followup.md` (NEW) | Plan doc following the convention (6-round audit-loop, stabilised, 7 findings, deferred items listed) | AGREE — convention adherence noted | Hermes addressed my soft pushback from PR #12 about missing plan docs. |

## Convention adherence

| Item | Status |
|---|---|
| Plan doc at `docs/plans/YYYY-MM-DD-<slug>.md` | ✓ |
| CHANGELOG `Unreleased` updated | ✓ |
| PR body uses template fields (Summary / Changes / Quality gates / Out of scope) | ✓ |
| Quality-gate checklist ticked | ✓ |
| Branch name | `hermes/release-hardening-followup-2` — uses Hermes-namespace, not the `feat/`/`fix/`/`docs/` convention in CONTRIBUTING.md. Pedantic style note, not a blocker. |

## Decision

**APPROVE.**

Highest-quality Hermes PR to date. Twelve substantive changes, every one of them either a real packaging fix, a regression test that closes a gap from a prior PR, or a factual correction. No substantive disagreement on any claim. Convention adherence is now full (PR #12's soft pushback addressed). The Stage 3 demo regression test is exemplary defensive testing — worth emulating elsewhere.

### Required actions before merge
None.

### Soft suggestions
- (Style only) Future Hermes branches could match the `feat/`/`fix/`/`docs/` prefix convention in CONTRIBUTING.md for symmetry with maintainer branches. Not blocking.
- The wheel-inspection test runs `python -m build` which adds ~5s to test time. Acceptable for a regression test of this importance; flag if test-suite latency becomes a friction point.

## Cross-iteration comparison

Iteration 1 — no prior iterations to compare against.

## Telemetry

Bot was not invoked (`ANTHROPIC_API_KEY` not set as repo secret at review time). This file is a manually-produced equivalent and serves as calibration data for tuning the v0 bot prompt when the secret is added.
