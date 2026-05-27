# Changelog

`v2.3.0` is the first GitHub tag/release. `pyproject.toml` also remains
`2.3.0` for this source distribution, but the repo is not on PyPI. Older
"hardening pass" sections below are historical commit-range labels, not package
releases.

## Unreleased

- CI: bump `actions/checkout` from v4 to v6.
- CI: bump `actions/setup-python` from v5 to v6.
- Docs: correct the CHANGELOG description of Issue templates landed in v2.3.0.
- Docs/examples: force the Stage 3 structural demo to use the placeholder
  comparator so it cannot make a real Claude comparator call under local config.
- Tools: PR review bot (v0) — every PR triggers a structured single-LLM
  forensic review via `tools/pr_review`, committed to the PR branch as
  `docs/reviews/<PR>-iter<K>.md`. Advisory only; the maintainer remains the
  merge gate. Prompt-injection defense via untrusted-content delimiters +
  regex tripwires. v1 will swap the single-LLM call for the full multi-stage
  council once Phases D + F land.

## v2.3.0 — 2026-05-27

**First public release** — tagged `v2.3.0` and published as a GitHub Release. No product-code behaviour change relative to the prior commits on `main`; this version cuts the tag and adds the professional-release scaffolding that makes the repo maintainable as an outside contribution surface.

### Added (community-health surfaces)
- `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml` + `config.yml` — new structured Issue forms; blank Issues turned off; contact links to Discussions and SECURITY.md. (Existing `.github/ISSUE_TEMPLATE/design-feedback.yml` was kept as-is — it already covers the 5 README design questions.)
- `.github/pull_request_template.md` — codifies the plan-doc-link + quality-gates-checklist habit established by PRs #7 and #8.
- `.github/CODEOWNERS` — auto-assigns review to `@Silberud` on every PR.
- `.github/dependabot.yml` — weekly pip + github-actions dependency updates.
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1, contact `igor.silberud@gmail.com`.
- `CITATION.cff` — machine-readable citation metadata; enables GitHub's "Cite this repository" widget.
- `.pre-commit-config.yaml` — local ruff/yaml/toml hooks so contributors don't fail CI on lint.
- `docs/release_process.md` — versioning policy + pre-flight checklist + cut/yank/hotfix procedures.
- README "Project conventions" section — surfaces all of the above in one table.

### Plan
- `docs/plans/2026-05-27-professional-release-prep.md` — the audit-loop + 14-task breakdown that drove this release.

## Public launch — 2026-05-26

Repo flipped from PRIVATE to PUBLIC after three Hermes Agent (GPT-5.5)
adversarial review passes. MIT, ©Igor Silberud. Discussions enabled;
seed Discussion #1 posted (Show and tell). CI green on all commits.
**The full council pipeline remains incomplete** — current release ships
the adapter skeleton + Stage 3 verifier-isolation path; Phases C / D /
F / G / H are on the roadmap (`ROADMAP.md`).

## v2.3 baseline — initial private staging (commit `49bce21`, 2026-05-24)

Phase A + Phase B + Phase E.0 + Phase E.1 of the 9-phase council plan.

### Added
- Orchestrator skeleton + supervisor entrypoint with graceful-fallback config loader.
- Six adapter interfaces: Claude / Gemini / GPT / Qwen contributing; Grok stub; Kimi verifier.
- Pydantic schemas: `VerifierInput` (frozen, `extra="forbid"`), `MemberResult`, `DroppedResult`, `VerifierAnswer`, `Vote`.
- Adapter base-class split (`ContributingAdapter` / `VerifierAdapter`) that gives `KimiAdapter` no `ask()` method.
- Stage 3 CoVe verifier with three-layer isolation (schema + adapter + content).
- `services/leak_filter.py` — n-gram window + role-marker leak detection (Phase E.1).
- `tests/test_cove_isolation.py` — 16 cases incl. 50-fixture Hypothesis fuzz on layers 1+2.
- `tests/test_leak_filter.py` — regression tests incl. patched leaky decomposer.
- `tests/test_adapter_smoke.py` — Phase B structural smoke tests.
- Runtime `isinstance(input, VerifierInput)` check in `KimiAdapter.ask_verifier`.
- Kimi endpoint allowlist (HTTPS-only, `api.moonshot.{ai,cn}` only unless `LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1`).
- Env-var-overridable Keychain service/account for Kimi.
- `confidence_parsed: bool` on `VerifierAnswer` so Phase E.2's real comparator can route unparsed answers.
- GitHub Actions CI: ruff (blocking) + pytest on Python 3.11 and 3.12.

### Documented
- `README.md` — design hypothesis, status table, 5 feedback questions, non-affiliation disclaimer, no-telemetry note.
- `docs/internal_spec_v2.2.md` — historical implementation directive (provenance preserved).
- `docs/design_notes.md` — citation status, structural-vs-prompt isolation rationale, force-verdicts rationale, quarantined-Chairman rationale.
- `docs/operator_setup.md` — auth requirements per seat + EX-001 / CG-001 / CG-002 / TRANS-001.
- `CONTRIBUTING.md` — pointers to load-bearing files; `_live/` test warning.

## Hardening Pass 1 — commit `a41cbd6` (2026-05-24)

Applied 18 items raised by Hermes Pass-1 adversarial review (20 findings;
19/20 CLOSED, #9 framing kept). Doc tightening, leak-filter introduced,
endpoint allowlist, `isinstance` runtime check, ruff made blocking,
audit-grade overclaim removed, spec relabelled internal.

## Hardening Pass 2 — commits `db2e7d2`, `6086c0b`, `7002578` (2026-05-25)

- `db2e7d2` — **argv → stdin** for Gemini and GPT adapters
  (Hermes finding #4). Prompt content no longer visible to `ps` / audit
  logs. Verified via live GPT smoke. **Resolved** the argv known
  limitation listed in the v2.3 baseline section above.
- `6086c0b` — **Phase E.2 real CoVe comparator** behind
  `[stages.stage3] comparator_mode = "real"`. ONE batched Claude call
  per Stage 3 session, returns per-question SUPPORT/CONTRADICT/NOT_RELATE
  judgments. Default stays placeholder; real mode remains opt-in. Later
  live-smoke validation landed in `400a67d`. If the real call fails the dispatcher logs
  and falls back to placeholder (consumers should inspect the returned
  `comparator_mode` field).
- `7002578` — `docs/hermes_findings_status.md` + `ROADMAP.md` for the
  deferred phases.

## Hardening Pass 2 re-review — commit `f05f1b9` (2026-05-26)

Applied 10 doc-consistency items Hermes raised on the post-Pass-2 state:
DISCUSSION_SEED reflects E.2 exists; README test count corrected to 55;
`[stages.stage3]` section added to `config.toml`; E.2 README status then
marked unit-tested and opt-in (live smoke landed later); leak-filter description
softened ("verbatim/procedural", not "drafter prose"); Kimi docstring
softened (schema constrains fields, not content); model-matrix Claude-
row copy/paste fixed; `hermes_findings_status` HEAD reference updated.

## Hardening Pass 3 — commits `587c2c8`, `0a989af` (2026-05-26)

- `587c2c8` — README per-file test count breakdown corrected
  (16 cove-isolation + 16 leak-filter + 13 comparator + 10 adapter-smoke).
- `0a989af` — `hermes_findings_status.md` trail-fidelity fix (an earlier
  global replace had corrupted the Pass-2 commit-history line).

## Public live-validation follow-up — commits `400a67d`, `76b817d` (2026-05-26)

- `400a67d` — added `orchestrator/tests/_live/test_comparator_live.py`,
  validating the real Claude comparator on hand-crafted SUPPORT /
  CONTRADICT / NOT_RELATE cases without spending Kimi quota.
- `76b817d` — cross-linked ROADMAP phases to Issues #2–#6 and reflected
  E.2 live-validation status in README.

## Public-launch polish — commit `ceb3bf0` (2026-05-26)

- GitHub repo description updated from "(private staging)" to public-
  honest framing.
- CHANGELOG restructured to use **hardening-pass labels with commit SHAs**
  instead of v2.3.1/v2.3.2/v2.3.3 (these were never released package
  versions; the package version stays `2.3.0`).
- **Removed the stale "argv known limitation"** from the bottom of the
  CHANGELOG — it was fixed in Pass 2's `db2e7d2` and was actively
  contradicting the README + code.
- `docs/hermes_findings_status.md` past-tensed: "Public flip completed
  on 2026-05-26."
- README TL;DR opening sentence softened to "building toward" framing
  so the orchestrator's incomplete state is visible *before* the status
  table.

## Known limitations (current public state)

- **Phase D (Stages 0/1/2/5):** not implemented — `council <prompt>` exits non-zero. See ROADMAP.md.
- **Phase C / F / G / H:** not implemented — see status table.
- **Grok seat:** stubbed (no subscription-OAuth path on X Premium+).
- **GPT model-pin:** Codex CLI 0.132.0 doesn't emit model id in stage events; the assertion logs a warning instead of asserting (CG-002).
- **Phase E.2 real comparator:** unit-tested and smoke-tested against live Claude on synthetic SUPPORT / CONTRADICT / NOT_RELATE cases. Default remains the placeholder; broader validation on real Stage 3 transcripts is future work.
- **Leak filter is heuristic**, not formal semantic noninterference. Paraphrastic leakage can still pass; the filter closes verbatim and procedural channels.
