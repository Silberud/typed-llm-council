# Council Review — PR #29, Iteration 1

**Title:** feat: add convergence ledger schema
**Author:** Andrjushapa (Hermes Agent)
**HEAD SHA:** 720de90e
**Base:** main (`d48ae49`) → HEAD: `feat/convergence-ledger-v0`
**Reviewed:** 2026-05-27
**Profile:** multi-provider council v0

---

## T — Triage

| Feature | Value |
|---|---|
| Files changed | 2 (additions only) |
| Lines | +547 / -0 |
| New files | `orchestrator/schemas/convergence.py` (268 lines), `orchestrator/tests/test_convergence_ledger.py` (279 lines) |
| Touches invariant files | no (additive only) |
| Author trust | known-collaborator (Hermes) |
| Substance | Substantive — introduces a new public schema namespace for the Convergence Council Protocol (ReviewVerdict / Severity / RunStatus / CouncilReview / JudgeDecision / ConvergenceLedger) |

---

## S — Security pre-check

**Tripwire scan:** `pi_flags: none`. PR body is straightforward; diff is pure schema + tests; no eval/exec/subprocess, no network calls, no Unicode tricks, no homoglyphs.

**Verdict:** SECURITY-CLEAR.

---

## Member verdicts (3 vendors, parallel)

### GPT-5.5 (Architect) — `codex exec` — **VERDICT: MODIFY (HIGH)**

> The PR is additive and has no obvious dependency cost, but its claimed "ledger invariants" are under-enforced: `ConvergenceLedger.ledger_state_is_consistent` only rejects `RUNNING` at `max_rounds`, while allowing a deserialized ledger to claim `FAILED_MAX_ROUNDS` before `max_rounds` or `BLOCKED` with no reason or blocking evidence (`orchestrator/schemas/convergence.py:200-218`). Dissent preservation is also mostly documentary: `JudgeDecision` does not require reviewer `required_changes` to be accounted for in either `material_required_changes` or `rejected_required_changes`, so material review objections can disappear structurally (`orchestrator/schemas/convergence.py:126-154`). `with_round` uses `model_copy(update=...)`, which bypasses Pydantic validation and weakens the promise that append operations obey the same invariants as deserialization (`orchestrator/schemas/convergence.py:251-267`). The tests cover happy-path convergence and some status mismatch cases, but not these terminal-status and review-to-judge accounting gaps (`orchestrator/tests/test_convergence_ledger.py:257-279`).
>
> **REQUIRED ACTIONS:**
> - Enforce valid `FAILED_MAX_ROUNDS` and `BLOCKED` ledger states, including a structural blocked reason if `BLOCKED` remains public API.
> - Add judge/review accounting validation so reviewer required changes cannot be silently dropped.
> - Rework `with_round` to validate the updated ledger or add tests proving no validator can be bypassed.

### Gemini 3.1 Pro (Researcher) — `gemini -p` — **VERDICT: APPROVE (HIGH)**

> The PR adds high-quality, Pydantic v2-based schemas for the Convergence Council Protocol, which perfectly aligns with the project's shift toward deterministic and auditable multi-round review loops. The logic for material vs. optional changes is strictly enforced via validators (e.g., `ReviewVerdict` consistency and `clean_round` strictness in `orchestrator/schemas/convergence.py`), and the `ConvergenceLedger` invariants (such as sequence checks and terminal state transitions) are thoroughly verified by the 10 new regression tests. Internal consistency is high, and the schema is purely additive, respecting the existing `{APPROVE, MODIFY, REJECT}` verdict set documented in `orchestrator/schemas/acemad_vote.py`.
>
> **REQUIRED ACTIONS:** None.
>
> **Optional:** Consider explicitly transitioning to `RunStatus.BLOCKED` if a `JudgeDecision` contains a `REJECT` verdict, as it is currently an unreachable but defined terminal status in the `with_round` logic.

### Qwen 3.6 (Analyst) — `ollama run qwen3.6:35b-a3b-coding-nvfp4` — **VERDICT: APPROVE (HIGH)**

> The diff introduces a robust, purely additive Pydantic v2 schema layer (`orchestrator/schemas/convergence.py`) with strict validation invariants enforced via `model_validator` and `Field` constraints. Control flow is deterministic and state-machine compliant, with comprehensive test coverage (`orchestrator/tests/test_convergence_ledger.py`) validating all terminal states, confidence caps, and round sequencing. Security patterns are clean, avoiding dynamic execution or external calls, and the code aligns closely with existing project idioms.
>
> **REQUIRED ACTIONS:** None.

---

## Aggregation

| Vote | Count |
|---|---|
| APPROVE | 2 (Gemini, Qwen) |
| MODIFY | 1 (GPT) |
| REJECT | 0 |
| DROPPED | 0 |

**Entropy: split** — 2 APPROVE / 1 MODIFY. Per slash command tie-breaking rules (see `.claude/commands/review-pr.md` Stage 3): "If the majority is APPROVE but a member has HIGH confidence in MODIFY/REJECT, downgrade to MODIFY."

GPT's MODIFY is **HIGH confidence** with substantive technical findings. Verdict downgrades.

---

## Chairman synthesis

The council split — but not randomly. **Gemini and Qwen evaluated the schema as a finished artifact** (does it model the right concepts? is the test coverage good?) and found it excellent. **GPT evaluated it as a contract** (do the invariants actually hold mechanically? can the schema be put into an invalid state?) and found three real gaps:

1. **`model_copy(update=...)` bypasses Pydantic validation** — `with_round` mutates state without re-running the validators. Deserialization runs validators; append doesn't. The append path can therefore produce ledgers that deserialization would reject. This is the most concrete finding.
2. **Reviewer→Judge accounting is structurally undocumented** — A reviewer's `required_changes` should be either accepted into `material_required_changes` or explicitly rejected via `rejected_required_changes`. Currently a `JudgeDecision` can quietly drop a reviewer's blocker by not mentioning it anywhere. The schema doesn't enforce the bookkeeping.
3. **`RunStatus.BLOCKED` is unreachable in `with_round`** — Both GPT and Gemini independently flagged this. Gemini called it optional; GPT called it a contract bug because the schema declares BLOCKED as a possible status but offers no transition into it.

These are all real findings. The schema is **good-and-shippable as v0 of the data model**, but it doesn't yet **fully enforce its own claimed invariants** — and the PR body explicitly says "this turns the convergence philosophy into a structural artifact instead of prose." That's the standard the schema should be held to.

The 2/3 APPROVE is genuine — for what the schema does, it's clean Pydantic, well-tested, idiomatic. The 1/3 MODIFY catches that the schema doesn't QUITE deliver on its strongest stated claim.

This is exactly the kind of finding the council exists to surface: **independent perspectives reach different evaluative depths** and the chairman's synthesis pulls out the most rigorous one. If only one reviewer had seen this PR (any vendor), there was a 2/3 chance they'd have rubber-stamped it.

---

## Decision

**MODIFY**

### Required actions before merge (GPT's findings, council-promoted to required)

1. **Make `with_round` re-validate the resulting ledger** (or add tests proving no `model_validator` can be bypassed by the `model_copy(update=...)` path). Suggested fix: `next_ledger = ConvergenceLedger(**self.model_dump() | {"rounds": next_rounds, "status": ...})` so Pydantic re-runs all validators.
2. **Enforce reviewer→judge accounting** in `JudgeDecision.model_validator`: for every reviewer `ReviewRequiredChange`, require it to appear by ID in either `material_required_changes.source_reviewers + .id` or `rejected_required_changes.id`. Add a regression test.
3. **Either implement the `RunStatus.BLOCKED` transition** (e.g. on JudgeDecision REJECT verdict, or on max_rounds with material dissent remaining) **or remove `BLOCKED` from the public enum** to keep the surface honest.

### Soft suggestions

- Consider adding a `BlockedReason` model required when `status == BLOCKED` (per GPT's suggestion).
- Optional: add a property method like `ConvergenceLedger.dissent_history` to surface dropped-vs-rejected dissent across rounds for telemetry purposes.

---

## Cross-iteration comparison

iter 1 — no prior reviews.

---

## Footer

- Council members invoked: 3/3 succeeded (no DROPPED)
- Members skipped (per spec): Grok (CG-001 stub), Kimi (non-voting verifier; CoVe deferred to v1)
- Total wallclock: ~3 minutes
- Slash command version: v0 multi-provider, latest from `.claude/commands/review-pr.md` post-PR-#28

**Anti-bias note:** This is the most interesting council outcome so far. **Two vendors said APPROVE; one said MODIFY with substantive technical findings.** A single-vendor reviewer would have a 2/3 chance of approving this PR without catching the `model_copy` validation bypass — which is exactly the failure mode the council is designed to prevent. Vendor diversity reached a different evaluative depth, and the chairman's synthesis pulled it up to a MODIFY verdict.

This is the council's value proposition demonstrated on substantive code, not just docs.
