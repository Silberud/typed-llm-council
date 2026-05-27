# Hermes adversarial review — findings status

Source: forensic review by GPT-5.5 (running in Hermes Agent / Nous Research)
against the v2.3.0 initial release, 24–25 May 2026. Hermes raised 20
numbered findings + a positive-findings summary.

This file tracks each finding's resolution status across the hardening
passes that followed:

- **Pass 1** (2026-05-24, commit `a41cbd6`): the initial Tier 1+2+3 pass.
- **Pass 2** (2026-05-25, commits `db2e7d2` + `6086c0b`): argv→stdin (#4)
  + real CoVe comparator (#3, Phase E.2).
- **Pass 2 docs** (2026-05-25, commit `7002578`): `hermes_findings_status.md`
  and `ROADMAP.md` added.
- **Pass 2 re-review fixes** (2026-05-26, commit `f05f1b9`): 10 doc-
  consistency items Hermes raised on the post-Pass-2 state.
- **Pass 3 fix** (2026-05-26, commit `587c2c8`): README per-file test-count
  breakdown corrected.

> **Self-audit history + three Hermes Agent reviews → public on 2026-05-26.**
> This file documents the maintainer's belief, cross-checked against
> Hermes's three Agent review passes. Hermes Pass-3 verdict on commit
> `587c2c8` was *"basically public-ready as a design-feedback / prototype
> repo."* The repo was flipped public on 2026-05-26 after a final
> doc-polish pass that addressed Hermes Pass-4's residual private-staging
> language. **Repo is now PUBLIC.**

## Findings table

| # | Finding (short) | Status | Where addressed |
|---|---|---|---|
| 1 | Verifier isolation claim materially overstated — schema blocks extra fields but doesn't constrain content of `verification_question`. | **CLOSED** (Pass 1 leak filter + Pass 2 marker refinement) | `services/leak_filter.py`, `stages/stage3_verification.py` |
| 2 | Tests don't exercise the dangerous boundary — `decompose_draft` mocked everywhere. | **CLOSED** (Pass 1) | `tests/test_leak_filter.py::test_stage3_aborts_when_decomposer_returns_leaky_question` |
| 3 | Stage 3 comparator is a confidence-threshold placeholder, not a real CoVe comparator. | **CLOSED** (Pass 2 — Phase E.2 real comparator) | `services/comparator.py::compare_answers_real`, dispatch in `stages/stage3_verification.py::compare_answers` |
| 4 | Prompt privacy leak via argv (Gemini, GPT). | **CLOSED** (Pass 2) | `adapters/gemini.py`, `adapters/gpt.py` — both now stdin |
| 5 | "Audit-grade transcript" overclaim when no transcript is written. | **CLOSED** (Pass 1) | README, architecture diagram, `docs/design_notes.md` |
| 6 | Issue template misaligned with README; "until Hermes ships" typo. | **CLOSED** (Pass 1) | `.github/ISSUE_TEMPLATE/design-feedback.yml`, README, DISCUSSION_SEED |
| 7 | H5 Resources provenance/IP needs explicit resolution. | **CLOSED** (Pass 1) | README acknowledgements section |
| 8 | "Single planning + build session" wording invites dismissal. | **CLOSED** (Pass 1) | README acknowledgements softened |
| 9 | "Type-level" language is partly rhetorical; runtime enforcement only. | **ADDRESSED w/ caveat** (Pass 1) | `adapters/kimi.py::ask_verifier` runtime `isinstance` check + `tests/test_adapter_smoke.py::test_kimi_ask_verifier_rejects_non_VerifierInput_at_runtime`. Framing kept ("structural adapter-level isolation") since runtime-enforced via Pydantic + class hierarchy. |
| 10 | Kimi confidence fallback bug (default 0.7 → silently treated as agreement). | **CLOSED** (Pass 1) | `adapters/kimi.py` default → 0.5; `schemas/stage_output.py::VerifierAnswer.confidence_parsed` flag |
| 11 | Config advertises Kimi keychain fields that code ignores. | **CLOSED** (Pass 1) | `supervisor.py::build_adapters` now wires through; `adapters/kimi.py::__init__` accepts kwargs |
| 12 | Configurable Kimi endpoint can exfiltrate the API key. | **CLOSED** (Pass 1) | `adapters/kimi.py::_validate_endpoint` HTTPS+allowlist; override via `LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1` |
| 13 | Docs make brittle third-party/provider claims. | **CLOSED** (Pass 1) | README non-affiliation banner; `docs/operator_setup.md` dated observations |
| 14 | Ultra-specific model names are fragile. | **CLOSED** (Pass 1) | README "Model compatibility matrix" with dated test status per seat |
| 15 | Spec reads like an internal implementation directive. | **CLOSED** (Pass 1) | `docs/council_spec_v2.2.md` → `docs/internal_spec_v2.2.md` with explicit "historical/internal" header |
| 16 | Stage numbering inconsistency (Stage 3 in design_notes vs spec). | **CLOSED** (Pass 1) | `docs/design_notes.md` Stage 3 → Stage 5 where synthesis is meant |
| 17 | "All 6 adapters" wording misleading (Grok stubbed, Kimi non-voting). | **CLOSED** (Pass 1) | README status-table row reworded: "five contributing interfaces + one verifier" |
| 18 | Lint is failing locally and CI ignores it. | **CLOSED** (Pass 1) | All ruff errors fixed; `.github/workflows/ci.yml` runs `ruff check .` as a blocking step |
| 19 | Quickstart should not use bare `python3` on macOS. | **CLOSED** (Pass 1) | README quickstart uses `python3.12 -m venv` explicitly + `pip install --upgrade pip setuptools wheel` |
| 20 | Positive findings list. | n/a — acknowledged | — |

## New findings surfaced during the hardening passes (not in Hermes's 20)

| ID | Finding | Status |
|---|---|---|
| N1 | Hypothesis fuzz found single-word "council" marker false-positiving on operator-side vocabulary ("COUNCIL000" as random `operator_prompt`). Pass 1 had `ROLE_MARKERS` as a flat list of single words + phrases. | **CLOSED** (Pass 2 — multi-word phrases only) |
| N2 | Pass 2's multi-word markers still false-positived on Hypothesis-generated "COUNCIL CONCLUDED" as `operator_prompt`. | **CLOSED** (`check_inputs_clean` operator-prompt path is now n-gram-only; role markers stay for the verification_question path where they're meaningful) |
| N3 | Test patches against `services.comparator.ClaudeAdapter.ask` fail because `ClaudeAdapter` is imported inside `compare_answers_real()` — patch target must be at source module. | **CLOSED** (`tests/test_comparator.py::_mock_claude` patches `orchestrator.adapters.claude.ClaudeAdapter.ask`) |

## What remains genuinely OPEN (post-public, 2026-05-26)

1. **Phases C / D / F / G / H** of the 9-phase plan. Roadmap at `ROADMAP.md`; tracking Issues #2–#6 are open.
2. **Independent external review.** The Hermes review chain was adversarial-AI review by a different model identity, not human review. Outside human or third-party adversarial review is welcome via Discussions or Issues.
3. **Broader E.2 comparator validation.** The real comparator has now passed a small live-Claude smoke (`tests/_live/test_comparator_live.py`) covering SUPPORT / CONTRADICT / NOT_RELATE on synthetic answers. Larger validation on real Stage 3 transcripts remains future work.

Public flip status: **complete** on 2026-05-26. Discussions are enabled and the repo is visible publicly.

## Test totals across passes

- v2.3.0 (initial): 24/24 structural + 1 live Stage 3 integration
- After Pass 1: 39/39 structural + 1 live Stage 3 integration
- After Pass 2 / public cleanup: 55/55 structural + 1 live Stage 3 integration + 2/2 live comparator tests
- After post-tag hardening (PRs #12/#13/#16/#17/#18): 63/63 structural + 1 live Stage 3 integration + 2/2 live comparator
- After slash-command pivot (PR #27, current): 60/60 structural + 1 live Stage 3 integration + 2/2 live comparator (PR #27 removed `test_pr_review_bot.py` along with the CI bot it tested)

## Recommended next reviewer action

The repo is now public. New reviewers — humans or other model identities
— are invited to read the code (start with the three files in
`CONTRIBUTING.md` *"Start by reading these three files"*), then open a
[Discussion](https://github.com/Silberud/typed-llm-council/discussions)
or an [Issue](https://github.com/Silberud/typed-llm-council/issues)
tagged `design-feedback`. The five design questions in the README are
the explicit invitation; pushback on the design hypothesis is the most
useful contribution.
