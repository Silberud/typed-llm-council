# Roadmap

The v2.3 implementation plan has 9 phases (A–I) per `docs/internal_spec_v2.2.md` §11.

**Currently shipped (v2.3.x):** Phase A + Phase B + Phase E (E.0 + E.1 + E.2 opt-in).
**Deferred to future sessions:** Phase C, Phase D, Phase F, Phase G, Phase H. Phase I (v1 migration) is n/a.

This file documents the planned scope of each deferred phase. Each phase
has acceptance criteria in spec §11 — match those.

---

## Phase C — Anonymizer service

**Scope.** Process-isolated anonymizer running on TCP `127.0.0.1:7711`,
RAM-only label map, launchd-managed for auto-restart. Holds the
`Response A` / `Response B` / `Response C` mapping during Stage 2 peer
review so the orchestrator can shuffle and re-label member responses
*without* the label map ever touching the filesystem.

**Files.**
- `orchestrator/services/anonymizer.py` — server process; accepts
  `register(member, response) → label` and `lookup(label) → member`
  RPCs; clears label map at session boundary.
- `orchestrator/clients/anonymizer_client.py` — supervisor-side client
  with retry + circuit-breaker.
- `~/.h5r-council/anonymizer/launchd.plist` — service definition.

**Dependencies.** None new (httpx + stdlib). `services/__init__.py`
already exists.

**Acceptance** (spec §11 Phase C). Anonymizer survives orchestrator
restart; label map never written to disk; supervisor can run a Stage 2
peer-review session against a randomly-relabelled response set and
recover authorship after Stage 3.

**Estimated effort.** ~6–10 hours.

---

## Phase D — Stages 0, 1, 2, 5

**Scope.** The four stages that turn Stage 3 into an end-to-end council
session. Without Phase D, `council <prompt>` deliberately exits non-zero.

- **Stage 0 — Framing.** Single Opus 4.7 call. Surfaces "is the question
  itself well-framed?" before any fan-out. Output: ≤1-paragraph framing
  note.
- **Stage 1 — Self-MoA-Seq Drafting.** Opus 4.7 only. Three samples
  S₁/S₂/S₃ at temp 0.7, aggregated D₁₂ at temp 0.3, then D₁₂₃ at temp
  0.3 (spec §6 Stage 1).
- **Stage 2 — D3 Advocate/Juror Critique.** Advocate = Opus 4.7,
  Jurors = the 4 contributing voters in parallel (90s timeout each).
  Drops members that error; spec §6 Stage 2 requires ≥3 voters to
  return for the round to proceed.
- **Stage 5 — PoLL Synthesis.** Rotating chair from
  {Claude, Gemini, GPT}. Deterministic selection from session_id seed;
  shadow chairs logged. Output: council consensus + dissent log +
  quarantined Chairman view + confidence.

**Files.**
- `orchestrator/stages/stage0_framing.py`
- `orchestrator/stages/stage1_drafting.py`
- `orchestrator/stages/stage2_advocate_juror.py`
- `orchestrator/stages/stage5_synthesis.py`
- Persona prompts in `members/<name>/system_prompts/`.

**Dependencies.** Phase C (anonymizer must exist for Stage 2 peer-review
order randomisation).

**Acceptance** (spec §11 Phase D). Single end-to-end `council <prompt>`
run completes Stage 0 → Stage 5; transcript is structured;
DROPPED-voter handling proceeds with ≥3.

**Estimated effort.** ~15–25 hours.

---

## Phase F — Stage 4 AceMAD aggregation + entropy flag

**Scope.** Per-voter Vote object with `verdict ∈ {APPROVE, REJECT,
MODIFY}`, self-belief `p_i`, peer-prediction distribution `q_i` over
the (other_voter, verdict) outcome space, Brier scoring, exponential
weight update, final verdict by argmax of `Σ wᵢ² · 𝟙{verdict_i = y}`.

**Important caveat (CG-001 carry-forward).** With Grok stubbed the
outcome space is **9 = 3 other voters × 3 verdicts**, NOT the spec's
12. The `services/peer_prediction.py` module must accept the outcome-
space size as a parameter, not hardcode 12. When the Skeptic seat
ships, that bumps to 12.

**Files.**
- `orchestrator/services/peer_prediction.py` (AceMAD math + entropy
  flag, parameterised on outcome-space size).
- Telemetry hooks at `telemetry/weight_trajectories/` and
  `telemetry/entropy_flags/`.

**Dependencies.** Phase D (need real Stage 2 verdicts to aggregate).

**Acceptance** (spec §11 Phase F). Synthetic test: truth-holder
dominates after 3 rounds; entropy flag fires on degenerate `qᵢ` and
does NOT block aggregation; weights overflow-capped at 1e10; η
configurable.

**Estimated effort.** ~10–15 hours.

---

## Phase G — Stage 6 FOCUS escalation + DRIFTJudge (Qwen Queue B)

**Scope.** FOCUS metric (Kaesberg et al., arXiv 2502.19559) for
real-time drift detection; DRIFTPolicy injection re-running Stage 4;
DRIFTJudge running on Qwen Queue B (same model as the contributor, but
isolated mutex queue + separate persona prompt). Hard cap: 1 escalation
+ 1 DRIFTPolicy attempt.

**Files.**
- `orchestrator/services/focus_metric.py`
- `orchestrator/services/drift_judge.py`
- `orchestrator/stages/stage6_escalation.py`
- Qwen Queue B mutex: already present in `adapters/qwen.py` —
  `_QWEN_MUTEX` is module-level and serialises Queue A (contributor)
  vs Queue B (judge).

**Dependencies.** Phase D, F.

**Acceptance** (spec §11 Phase G). Queue B works without blocking
Queue A; DRIFTJudge persona differs from Qwen-contributor persona;
FOCUS ≥ 0.5 Spearman with manual annotations on a small labelled set;
hard cap enforced.

**Estimated effort.** ~10–15 hours.

---

## Phase H — Telemetry + bootstrap

**Scope.** SQLite WAL session database + `council-eval --bootstrap`
against a ≥10-session labelled corpus. Includes per-stage timing,
DROPPED-voter counts, entropy-flag aggregates, comparator-mode
distribution, FOCUS scores.

**Files.**
- `orchestrator/services/telemetry.py` — DB schema + writers.
- `~/.h5r-council/telemetry/sessions.db` (WAL).
- `bin/council-eval` (currently a placeholder).

**Dependencies.** Phase D minimum; Phase F + G ideally for full schema.

**Acceptance** (spec §11 Phase H). All sessions emit a row to
`sessions.db`; weight trajectories written; entropy flags written;
`n_entropy_flags` column populated; `council-eval --bootstrap` reads
≥10 labelled sessions from `telemetry/labelled/pass_fail.jsonl`.

**Estimated effort.** ~8–12 hours.

---

## What's NOT on the roadmap

- **Public spec rewrite.** `docs/internal_spec_v2.2.md` is the
  maintainer's implementation directive. A polished public spec
  could be a Phase E+ deliverable but isn't currently planned.
- **Web UI / TUI.** This is a Python orchestrator. UI is out of scope.
- **Multi-tenant.** Single-operator workstation tool. Multi-user
  deployment is out of scope.
- **Cross-platform parity.** macOS + Linux (WSL2). Native Windows is
  out of scope.

---

Total deferred effort: **~50–80 hours** across Phases C–H. Each is its
own session; coordination across them is sequential per the dependency
graph above.
