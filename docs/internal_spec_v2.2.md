# H5R LLM Council v2.2 — Internal Implementation Specification (historical)

> **READER — please note:** This file is the **internal implementation
> directive** the maintainer originally wrote to scaffold the v2.3 code with
> Claude Code. It is preserved here for provenance / historical reference,
> not as a polished public specification. It addresses Claude Code as the
> implementer ("You are Claude Code…") and contains references to operator-
> specific exceptions (the API-key path documented in
> `docs/operator_setup.md`). For the public-facing design narrative see
> `docs/design_notes.md` and the README. A cleaned public spec is a
> potential Phase E+ deliverable.

**For:** Claude Code (autonomous implementation agent)
**Operator:** Igor Silberud
**Date:** 24 May 2026
**Document status:** v2.2 — revision of v2.1 with entropy-flag and AceMAD caveat
**Implementation mode:** Phased; gated by acceptance criteria

---

## Diff from v2.1

| Section | Change |
|---|---|
| §6 Stage 4 | AceMAD discrete-form caveat documented; sample-space implications flagged |
| §7.5 | Entropy flag for q_i distributions added to AceMAD module |
| §11 Phase F | New acceptance criterion: entropy-flag fires correctly on synthetic degenerate q_i |
| §12 Risks | New row: AceMAD sample-space scaling untested by source paper |
| §14 First-30 instrumentation | Manual q_i review replaced with automated flag + manual review of flagged only |
| §15 Failure modes | Entropy-flag triggered: handling protocol |

All other sections unchanged from v2.1. This document is self-contained — Claude Code does not need v2.1 to implement v2.2.

---

## 0. How to use this document

You are Claude Code. Read end-to-end before writing any code.

Implementation rules:

1. **Phased implementation.** Do not start Phase N+1 until Phase N's acceptance criteria pass. See §11.
2. **Ask before deviating.** Stop and ask the operator if a spec section is ambiguous.
3. **No new dependencies without justification.** Dependency list in §9.1.
4. **All paths are absolute** under `~/.h5r-council/`.
5. **Python 3.11+ only.**
6. **Subscription-only auth.** No API keys.
7. **One commit per acceptance-criteria block.**
8. **No bypass paths.** No "simple mode," no "degraded mode" past documented DROPPED-member handling.

---

## 1. Architecture summary

The v2.2 council replaces a Claude-Code-Chairman-with-shell-wrappers architecture (v1) with a **decoupled orchestrator** running as a long-lived Python process, invoking each council member via its native subscription-bound CLI. Claude Code's role is reduced from "Chairman of everything" to "operator interface and one of four rotating synthesisers."

Six load-bearing concepts:

| Concept | Paper | Role |
|---|---|---|
| **Self-MoA-Seq** sliding-window drafting | Li, Lin, Xia, Jin, arXiv 2502.00674 | Drafter (Stage 1) |
| **D3 advocate–juror split** | Bandi et al., arXiv 2410.04663 | Stage 2 critique |
| **CoVe factored verification** | Dhuliawala et al., arXiv 2309.11495 | Stage 3 verifier (K2.6) |
| **AceMAD peer-prediction** | Liu, Zhang, Wu et al., arXiv 2603.06801 | Stage 4 aggregation |
| **FOCUS metric** | Kaesberg, Becker et al., arXiv 2502.19559 | Drift detector |
| **PoLL rotating-jury synthesis** | Verga et al., arXiv 2404.18796 | Stage 5 synthesiser rotation |

Confidence on AceMAD performance magnitude: moderate. Confidence on the *mechanism* in the discrete-verdict / 12-outcome sample space we apply: lower than the paper's claimed regime — see §6 Stage 4 caveat and §12 risk row. Treat AceMAD as the architecturally most adventurous component.

---

## 2. The seven design invariants (non-negotiables)

1. **No model identity holds two contributing roles in the same session.** Clarification: when a model identity serves both a contributing role and a non-contributing role (DRIFTJudge), the invocations run in isolated Ollama queues with independent personas. Documented structural compromise; not a hidden violation.
2. **Verifier seat (K2.6) is non-voting.** Does not enter AceMAD. Outputs gate revision, not synthesis.
3. **Anonymisation is process-isolated.** Label map lives in separate process with no filesystem access to member working directories.
4. **Subscription-only auth.** No API keys.
5. **All session state is durable.** Every stage writes JSON before invoking the next.
6. **Synthesis chair rotates per session.** Selection logged with random seed; shadow chairs logged under 3 alternative seeds.
7. **No member sees another member's reasoning trace, system prompt, or persona before Stage 4.**

---

## 3. Council roster (locked at top-tier)

Six seats. Five contributing, one verifying.

| Role | Seat | Model | Auth | Locality | Voting? |
|---|---|---|---|---|---|
| Drafter / Self-MoA-Seq | **Claude** | Opus 4.7 via Claude Code CLI | Claude Code session | Workstation | Yes |
| Researcher | **Gemini** | Gemini 3.1 Pro via `gemini-cli` | Google OAuth | Cloud | Yes |
| Architect | **GPT** | GPT-5.5 via Codex CLI (pinned, §9.2) | ChatGPT Pro OAuth | Cloud | Yes |
| Analyst | **Qwen** | Qwen 3.6:35b-a3b via Ollama, queue A | none | M3 Max GPU | Yes |
| Skeptic | **Grok** | Latest Grok via xAI CLI | xAI OAuth | Cloud | Yes |
| **Verifier (CoVe)** | **Kimi K2.6** | Moonshot Kimi K2.6 via Kimi CLI | Moonshot OAuth | Cloud | **No** |

**DRIFTJudge** runs on Qwen 3.6:35b-a3b via Ollama queue B — same model, separate queue, separate persona, never concurrent with Qwen-as-contributor.

---

## 4. System topology and process isolation

(Topology diagram unchanged from v2.1.)

Key components:
- Orchestrator (Python 3.11 asyncio, tmux-attached, long-lived PID)
- Six member CLIs invoked as subprocesses with `cwd` scoped to per-member workdirs (`chmod 700`)
- Anonymizer service (separate process, TCP 127.0.0.1:7711, RAM-only label map, launchd-managed)
- Ollama with Qwen — orchestrator-side asyncio mutex serialises Queue A (contributor) vs Queue B (DRIFTJudge)
- SQLite WAL telemetry at `~/.h5r-council/telemetry/sessions.db`

---

## 5. On-disk layout

```
~/.h5r-council/
├── orchestrator/
│   ├── supervisor.py
│   ├── config.toml
│   ├── stages/
│   │   ├── stage0_framing.py
│   │   ├── stage1_drafting.py
│   │   ├── stage2_advocate_juror.py
│   │   ├── stage3_verification.py
│   │   ├── stage4_acemad.py
│   │   ├── stage5_synthesis.py
│   │   └── stage6_escalation.py
│   ├── services/
│   │   ├── anonymizer.py
│   │   ├── drift_judge.py
│   │   ├── focus_metric.py
│   │   ├── peer_prediction.py        # AceMAD math + entropy flag
│   │   ├── qwen_mutex.py
│   │   └── telemetry.py
│   ├── adapters/
│   │   ├── base.py
│   │   ├── claude.py
│   │   ├── gemini.py
│   │   ├── gpt.py
│   │   ├── qwen.py
│   │   ├── grok.py
│   │   └── kimi.py                   # Typed VerifierInput only
│   ├── schemas/
│   │   ├── stage_output.py
│   │   ├── acemad_vote.py
│   │   └── verifier_input.py         # K2.6 isolation: typed input
│   └── tests/
│       ├── fixtures/
│       ├── test_cove_isolation.py    # Critical CI check
│       └── test_*.py
├── members/
│   ├── claude/    {system_prompts/, role.md, workdir/}
│   ├── gemini/
│   ├── gpt/
│   ├── qwen/
│   ├── grok/
│   └── kimi/
├── anonymizer/
├── transcripts/
│   ├── YYYY-MM-DD/
│   │   └── session_<ulid>.json
│   └── archive/
├── telemetry/
│   ├── sessions.db
│   ├── labelled/pass_fail.jsonl
│   ├── weight_trajectories/
│   │   └── session_<ulid>.jsonl
│   ├── entropy_flags/                # NEW v2.2
│   │   └── session_<ulid>.jsonl
│   └── judge_model/
├── docs/
│   ├── council_spec_v2.2.md          # This document
│   ├── stage_protocols/
│   ├── operator_runbook.md
│   └── archive/
│       ├── council_spec_v2.0.md
│       └── council_spec_v2.1.md
└── bin/
    ├── council
    ├── council-eval
    └── council-replay
```

All directories `chmod 700`.

---

## 6. The seven-stage protocol

```
Stage 0      Stage 1            Stage 2          Stage 3         Stage 4          Stage 5            Stage 6
[Framing] -> [Self-MoA-Seq] ->  [D3 critique] -> [CoVe verify] -> [AceMAD vote] -> [PoLL synth.] -> [FOCUS escalate?]
 Opus 4.7    Opus 4.7           Advocate         K2.6 only        all 5 voters     rotating chair    if drift OR
 mandatory   + 3 samples        (Drafter)        factored input   p_i + q_i        from contrib.     LOW conf;
                                + 4 jurors       (no draft        Brier scored     pool (no Qwen     capped 1 round
                                in parallel      context)         exp weights      no K2.6)          + DRIFTPolicy
                                                                  + entropy flag                     (Qwen Queue B)
```

### Stage 0 — Framing & Premise Check
- **Actor:** Opus 4.7
- **Output:** Framing note (≤1 paragraph)

### Stage 1 — Self-MoA-Seq Drafting
- **Actor:** Opus 4.7 only
- **Algorithm:** Sliding-window aggregation per Li et al. 2502.00674 §4.2:
  1. Sample S₁, S₂ at temp 0.7 (parallel)
  2. Aggregate (S₁, S₂) → D₁₂ at temp 0.3
  3. Sample S₃ at temp 0.7
  4. Aggregate (D₁₂, S₃) → D₁₂₃ at temp 0.3
- **Default N:** 3 samples

### Stage 2 — D3 Advocate-Juror Critique
- **Actors:** Advocate = Opus 4.7; Jurors = Gemini 3.1 Pro, GPT-5.5, Qwen (Queue A), Grok
- **Timeout:** 90s per juror
- **DROPPED handling:** continue iff ≥3 voters return; else abort

### Stage 3 — CoVe Factored Verification (K2.6)
- **Actor:** K2.6 only. **Non-voting.**
- **Critical invariant:** K2.6 receives ONLY a typed `VerifierInput` containing `operator_prompt` and `verification_question` fields. **Never** Draft D, framing, or any prior stage output. Enforced at the adapter type-signature level + CI test (see §7.6, `test_cove_isolation.py`).
- **Algorithm:**
  1. Orchestrator (using Opus 4.7 as decomposer) decomposes Draft D into 5–10 atomic verification questions
  2. K2.6 answers each independently (batched in groups of 5, parallel within batch)
  3. Orchestrator compares K2.6's answers against Draft D's claims
- **Output:** Verification report
- **Action:** Any `disagree` flag triggers Stage 5 revision

### Stage 4 — AceMAD Verdict Aggregation

**IMPORTANT CAVEAT (new in v2.2):** The original AceMAD paper (Liu et al. 2603.06801) benchmarks the peer-prediction mechanism on multiple-choice QA tasks with verdict-space cardinality 4–10. Our application uses a verdict space of {APPROVE, REJECT, MODIFY} (cardinality 3) but a *peer-prediction sample space* of size **(N_other_voters) × (N_verdicts) = 4 × 3 = 12 outcomes**, which is larger than the paper's tested regime. The submartingale-drift property is *theoretically robust* to sample-space size (the math depends on strictly proper scoring rules, which Brier is), but empirically untested at this dimension. The first-30-session weight-trajectory analysis (§14) is the primary detector for whether truth-holders rise correctly in our regime. If trajectories show degenerate behaviour (no voter dominates, or wrong voter dominates), the η parameter and / or the peer-prediction schema must be re-evaluated.

- **Actors:** All 5 contributing voters
- **Per-voter output:**
  - verdict ∈ {APPROVE, REJECT, MODIFY}
  - self_belief p_i ∈ [0, 1]
  - peer_prediction q_i: discrete distribution over 12 (other_voter, verdict) outcomes; must sum to 1.0
- **Algorithm:**
  1. Realised distribution Q* computed from observed verdicts
  2. Brier score S_i = -Σₖ (q_i[k] - Q*[k])²
  3. **Entropy flag** computed for each q_i (see §7.5; flagged but not blocked)
  4. Weight update: w_i^{(t+1)} = w_i^{(t)} · exp(η · S_i)
  5. Final verdict: argmax_y Σᵢ (w_i^{(t)})² · 𝟙{verdict_i = y}
- **Default η:** 1.0 (configurable, logged per session)
- **Logging:** Weight trajectories to `telemetry/weight_trajectories/`; entropy flags to `telemetry/entropy_flags/`

### Stage 5 — PoLL Synthesis (rotating chair)
- **Actor:** One of {Claude/Opus 4.7, Gemini 3.1 Pro, GPT-5.5, Grok}. Qwen excluded (latency); K2.6 excluded (Verifier-only).
- **Selection:** Deterministic from session_id seed; shadow chairs logged
- **Output:** Council consensus, dissent log, chair's independent judgement (quarantined, ≤1 paragraph), CoVe-addressed revisions, confidence

### Stage 6 — FOCUS-Gated Escalation
- **Trigger:** LOW confidence OR chair substantively dissents OR FOCUS_r < -0.3
- **Algorithm:**
  1. If drift: DRIFTPolicy (Qwen Queue B) injects corrective meta-instruction; re-run Stage 4 only
  2. If LOW without drift: re-pose disagreement, prior outputs visible, one round
- **Hard cap:** 1 escalation + 1 DRIFTPolicy attempt

### Confidence calibration (Stage 5)

| Verdict | Criteria |
|---|---|
| HIGH | AceMAD unanimous post-weight; Chair no reservation; CoVe 0 disagreements |
| MEDIUM | Not unanimous OR Chair reservation OR CoVe ≤2 disagreements |
| LOW | AceMAD weighted disagreement >30% OR CoVe ≥3 disagreements OR FOCUS triggered |

---

## 7. Component specifications

### 7.1 Orchestrator (`orchestrator/supervisor.py`)

(Unchanged from v2.1. See v2.1 §7.1.)

### 7.2 Member adapters

Per-adapter specifics with model pinning:

| Adapter | CLI | Model pin | Auth check |
|---|---|---|---|
| `claude.py` | `claude --model opus-4-7 --print --output-format json` | opus-4-7 explicit | `claude --auth-status` |
| `gemini.py` | `gemini --model gemini-3.1-pro --prompt-file <tmp>` | gemini-3.1-pro explicit | `gemini --check-auth` |
| `gpt.py` | `codex chat --model gpt-5.5 --json` + post-call assertion (§9.2) | gpt-5.5 explicit + verified | `codex login --check` |
| `qwen.py` (Queue A) | HTTP POST `localhost:11434/api/generate` model=qwen3.6:35b-a3b | model in payload | Ollama `/api/tags` |
| `grok.py` | xAI CLI; log response model identifier | latest (logged) | `xai-cli auth status` |
| `kimi.py` | Kimi CLI; accepts ONLY `VerifierInput` typed model (§7.6) | kimi-k2.6 explicit | `kimi auth check` |

### 7.3 Self-MoA-Seq drafter

(Unchanged from v2.1.)

### 7.4 Anonymizer service

(Unchanged from v2.1.)

### 7.5 AceMAD peer-prediction module (`services/peer_prediction.py`)

```python
from dataclasses import dataclass
from typing import Literal
import math, json
from pathlib import Path
from collections import defaultdict

OUTCOME_SPACE_SIZE = 12  # 4 other voters × 3 verdicts — must match council size

@dataclass
class Vote:
    voter: str
    verdict: Literal["APPROVE", "REJECT", "MODIFY"]
    self_belief: float          # p_i ∈ [0, 1]
    peer_prediction: dict       # {(other_voter, verdict): prob}; sums to 1.0
    rationale: str

def shannon_entropy(distribution: dict[any, float]) -> float:
    """Shannon entropy in nats. distribution values must sum to ~1.0."""
    return -sum(p * math.log(p) for p in distribution.values() if p > 0)

def entropy_flag(q_i: dict, voter_name: str, session_id: str) -> dict | None:
    """
    Compute entropy flag for a peer-prediction distribution.
    Flags two failure modes:
      (a) suspiciously low entropy (over-concentrated peer prediction)
      (b) spike concentration (single outcome > 0.7 probability)
    
    Returns flag dict if flagged, None otherwise.
    Does NOT block aggregation — flags only.
    """
    h = shannon_entropy(q_i)
    max_h = math.log(OUTCOME_SPACE_SIZE)  # ≈ 2.485 nats for size=12
    low_entropy_threshold = 0.6 * max_h    # ≈ 1.491 nats
    spike_threshold = 0.7
    
    max_prob = max(q_i.values()) if q_i else 0
    
    flagged_reasons = []
    if h < low_entropy_threshold:
        flagged_reasons.append(f"low_entropy: H={h:.3f} < {low_entropy_threshold:.3f}")
    if max_prob > spike_threshold:
        flagged_reasons.append(f"spike: max_prob={max_prob:.3f} > {spike_threshold}")
    
    if not flagged_reasons:
        return None
    
    flag = {
        "session_id": session_id,
        "voter": voter_name,
        "entropy_nats": h,
        "max_entropy_possible": max_h,
        "max_outcome_prob": max_prob,
        "reasons": flagged_reasons,
        "distribution": q_i,
    }
    
    # Persist
    flag_path = (Path.home() / ".h5r-council" / "telemetry" /
                 "entropy_flags" / f"session_{session_id}.jsonl")
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    with flag_path.open("a") as f:
        f.write(json.dumps(flag) + "\n")
    
    return flag

def brier_score(prediction: dict, realised: dict) -> float:
    keys = set(prediction.keys()) | set(realised.keys())
    return -sum((prediction.get(k, 0.0) - realised.get(k, 0.0))**2 for k in keys)

def aggregate(votes: list[Vote], eta: float, prior_weights: dict | None,
              session_id: str) -> dict:
    weights = prior_weights or {v.voter: 1.0 for v in votes}
    realised = compute_realised(votes)
    
    flags = []
    trajectory_path = (Path.home() / ".h5r-council" / "telemetry" /
                       "weight_trajectories" / f"session_{session_id}.jsonl")
    trajectory_path.parent.mkdir(parents=True, exist_ok=True)
    
    with trajectory_path.open("a") as f:
        for v in votes:
            # Entropy flag (logs but does not block)
            flag = entropy_flag(v.peer_prediction, v.voter, session_id)
            if flag:
                flags.append(flag)
            
            s_i = brier_score(v.peer_prediction, realised)
            old_w = weights[v.voter]
            weights[v.voter] = min(old_w * math.exp(eta * s_i), 1e10)  # overflow cap
            
            f.write(json.dumps({
                "voter": v.voter, "eta": eta, "brier": s_i,
                "weight_pre": old_w, "weight_post": weights[v.voter],
                "self_belief": v.self_belief,
                "peer_pred": v.peer_prediction,
                "realised": realised,
                "entropy_flagged": flag is not None,
            }) + "\n")
    
    verdict_scores = defaultdict(float)
    for v in votes:
        verdict_scores[v.verdict] += weights[v.voter] ** 2
    
    return {
        "winner": max(verdict_scores, key=verdict_scores.get),
        "weights": weights,
        "verdict_scores": dict(verdict_scores),
        "entropy_flags": flags,
    }

def compute_realised(votes: list[Vote]) -> dict:
    """Realised peer distribution: for each (voter, verdict) pair, 
    the fraction of voters who actually produced that verdict (excluding self).
    Simplification: uses the empirical verdict distribution as the realised."""
    total = len(votes)
    counts = defaultdict(int)
    for v in votes:
        counts[v.verdict] += 1
    # Convert to (voter, verdict) keys — assigning the same marginal to each
    # other-voter pair since we observe one verdict per voter in this round
    result = {}
    for v in votes:
        for vv in votes:
            if vv.voter == v.voter:
                continue
            key = (vv.voter, vv.verdict)
            result[key] = 1.0 / (total - 1) if total > 1 else 0.0
    # Normalise
    total_mass = sum(result.values())
    if total_mass > 0:
        result = {k: v / total_mass for k, v in result.items()}
    return result
```

**Implementation notes:**

1. The `compute_realised` function uses a simplification: empirical observed verdicts treated as the realised peer distribution. The paper's continuous-distribution formulation differs; this discrete adaptation is documented in §6 Stage 4 caveat as a structural assumption.
2. Entropy threshold values (`0.6 × max_h`, `0.7` spike) are starting defaults — tunable in `config.toml` after first 30 sessions of telemetry.
3. The flag does NOT block aggregation — degenerate q_i still produces a Brier score (just a bad one), and the weight update proceeds. The flag surfaces for operator review only.

### 7.6 K2.6 Verifier (`adapters/kimi.py` + `schemas/verifier_input.py`)

**Typed input contract:**

```python
# schemas/verifier_input.py
from pydantic import BaseModel, Field

class VerifierInput(BaseModel):
    """The ONLY input shape the Kimi adapter accepts.
    
    Forbidden: any field referring to Draft D, framing, council deliberations,
    persona prompts, advocate defence, juror critiques.
    
    The Pydantic model is frozen with `model_config = ConfigDict(frozen=True, extra="forbid")`
    so unknown fields raise ValidationError.
    """
    model_config = {"frozen": True, "extra": "forbid"}
    
    operator_prompt: str = Field(min_length=1, max_length=10000)
    verification_question: str = Field(min_length=1, max_length=2000)
```

**Adapter signature:**

```python
# adapters/kimi.py
class KimiAdapter(MemberAdapter):
    name = "kimi"
    
    async def ask_verifier(self, input: VerifierInput) -> VerifierAnswer:
        """The ONLY method exposed for Stage 3 calls.
        Does not accept generic prompt; type system enforces input shape."""
        # ... CLI invocation with input.operator_prompt + input.verification_question only
    
    # Note: this adapter has NO `ask()` method matching the base class —
    # it is intentionally restricted to verifier role only.
```

CI test enforces type-level isolation: see standalone artifact `test_cove_isolation.py`.

### 7.7 DRIFTJudge (Qwen Queue B)

(Unchanged from v2.1. See v2.1 §7.7.)

### 7.8 PoLL synthesizer

(Unchanged from v2.1.)

### 7.9 Telemetry pipeline

Schema (additions for v2.2 in **bold**):

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    chair TEXT NOT NULL,
    final_verdict TEXT NOT NULL,
    confidence TEXT NOT NULL,
    dissent_rate REAL,
    convergence_delta REAL,
    duration_s REAL,
    n_dropped_voters INTEGER DEFAULT 0,
    escalated INTEGER DEFAULT 0,
    drift_detected INTEGER DEFAULT 0,
    shadow_chairs TEXT,
    eta_used REAL DEFAULT 1.0,
    qwen_queue_contention_events INTEGER DEFAULT 0,
    n_entropy_flags INTEGER DEFAULT 0,        -- NEW v2.2
    transcript_path TEXT NOT NULL
);
```

Plus the new file-system structure:
- `telemetry/entropy_flags/session_<ulid>.jsonl` — one line per flagged q_i

---

## 8. Stage-by-stage prompt contracts

(Unchanged from v2.1.)

---

## 9. Build & deployment

### 9.1 Dependencies

```toml
[project]
name = "h5r-council"
version = "2.2.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic >= 2.6",
    "tomli >= 2.0",
    "python-ulid >= 2.2",
    "httpx >= 0.27",
    "sentence-transformers >= 3.0",
    "rich >= 13.7",
    "uvloop >= 0.19",
]

[project.optional-dependencies]
dev = ["pytest >= 8.0", "pytest-asyncio >= 0.23", "hypothesis >= 6.100", "ruff >= 0.4"]
```

(Added `hypothesis` for property-based fuzzing in CI assertion tests.)

### 9.2 Codex CLI model pinning

GPT-5.5 must be explicitly selected. After each call, parse Codex's response metadata (`model_used` field) and assert it equals `gpt-5.5`. If mismatch, retry once with explicit selection; if persistent, mark stage DROPPED for that adapter. Non-negotiable.

### 9.3 Bootstrap script

(Unchanged from v2.1, plus mkdir for `telemetry/entropy_flags/`.)

### 9.4 Claude Code integration

(Unchanged from v2.1.)

---

## 10. Latency budget

(Unchanged from v2.1: ~6 min nominal, ~8.7 min with escalation. Entropy flag computation is O(n_voters) and negligible.)

---

## 11. Acceptance criteria (phase gates)

**Phase A — Skeleton + Orchestrator:** (unchanged from v2.1)

**Phase B — Member adapters:**
- All 6 adapters pass smoke tests
- Model-pin assertion works for each (Codex catches drift)
- Auth-check returns False not exception when broken
- Timeouts + DROPPED handling
- **Kimi adapter rejects any input that isn't a `VerifierInput` (Pydantic ValidationError)**

**Phase C — Anonymizer:** (unchanged)

**Phase D — Stages 0, 1, 2, 5:** (unchanged)

**Phase E — Stage 3 CoVe verifier:**
- `test_cove_isolation.py` passes (see standalone artifact)
- Type-level enforcement: Kimi adapter ONLY accepts `VerifierInput`
- Substring leak-check (belt-and-suspenders): K2.6 prompt contains no draft/framing text
- Hypothesis property-based fuzzing: 50 random fixtures, isolation holds in all
- Decomposer produces 5–10 questions
- Comparator flags known factual errors

**Phase F — Stage 4 AceMAD:**
- Voters return p_i and q_i in valid schema
- Brier scoring; weights update with overflow cap; final verdict uses w²
- Weight trajectories logged
- **Entropy flag fires on synthetic degenerate q_i** (uniform-spike at one outcome → spike threshold triggers; near-uniform distribution does NOT trigger)
- **Entropy flag does NOT block aggregation** — flagged session still produces a winner
- Synthetic test: truth-holder dominates after 3 rounds
- η configurable via config.toml and logged

**Phase G — Stage 6 FOCUS escalation (Qwen Queue B):**
- Queue B works without interfering with Queue A
- DRIFTJudge persona separate from Qwen-contributor persona
- FOCUS scores ≥0.5 Spearman with manual annotations
- All 3 DRIFTPolicy interventions inject correctly
- Hard cap enforced

**Phase H — Telemetry & bootstrap:**
- All sessions emit row to sessions.db
- Weight trajectories written
- **Entropy flags written; `n_entropy_flags` column populated**
- Shadow chairs logged
- `council-eval --bootstrap` works with ≥10 labelled sessions

**Phase I — v1 migration:** (unchanged)

---

## 12. Risks and open issues

| Risk | Severity | Mitigation |
|---|---|---|
| AceMAD's q_i prompt fails on Qwen (degenerate peer-prediction) | High | Entropy flag (§7.5) surfaces automatically; first-30-session telemetry inspects flagged cases; if Qwen consistently flagged, exclude from Brier scoring |
| **AceMAD sample-space scaling untested by source paper** | **High** | Paper benchmarks 4–10 verdict outcomes; we use 12 (voter, verdict) peer-prediction outcomes. Weight trajectories monitored per session; if truth-holders fail to rise across first 30 sessions, escalate η tuning or schema re-design |
| Qwen overload under parallel DRIFTJudge + contributor | High | QwenMutex serialises Queue A/B; telemetry tracks contention |
| K2.6 latency degrades Stage 3 | Medium | Batch in groups of 5; parallel within |
| FOCUS on Qwen is noisy | Medium | ≥0.5 Spearman target (lower than ideal); re-baseline after first 30 |
| Self-MoA-Seq blows Claude Code rate limits | Medium | N=3 default; verify on first 10 |
| Codex CLI silently uses wrong model | High | Model-pin assertion non-negotiable |
| Grok model version changes | Medium | Log response model identifier |
| Anonymizer crash mid-session | Low | launchd auto-restart; session aborts |

**Open issues NOT solved:**

1. AceMAD η = 1.0 is a guess; tune post-Phase F
2. Entropy flag thresholds (0.6, 0.7) are starting defaults; tune post-Phase H
3. No ground-truth dataset; operator labels noisy
4. DRIFTPolicy heuristics may not generalise
5. No mobile / remote operator access
6. No cross-session learning

---

## 13. Migration plan from v1

(Unchanged from v2.1.)

---

## 14. First-30-sessions instrumentation profile

| Telemetry | What to capture | Why |
|---|---|---|
| **Automated entropy flag** | Every q_i checked at aggregation time; only flagged cases surface for manual review | Replaces v2.1's "manually review 10 q_i per session" with targeted review; flag fires automatically when q_i shows low entropy OR spike concentration |
| Manual review of flagged q_i | Operator reviews flagged events in `telemetry/entropy_flags/` | Confirms automated flag is calibrated; tunes thresholds |
| Weight trajectory delta | Plot per-voter weight evolution across all 30 sessions | Detect runaway η or systematic voter dominance |
| **AceMAD truth-holder test** | At sessions 10, 20, 30: identify sessions where operator labelled outcome diverges from AceMAD verdict; check whether the voter holding the correct verdict accrued higher weight | Empirical test of the AceMAD mechanism in our 12-outcome regime |
| Codex model-pin compliance | 100% of GPT calls verify `model_used == gpt-5.5` | Catch silent downgrades |
| Qwen queue contention | Log every Queue B block waiting for Queue A | If >20% sessions show >5s contention, escalate |
| CoVe disagreement rate | % of K2.6 answers disagreeing with Draft D | Calibrate decomposer aggressiveness |
| Chair distribution | Verify each of 4 chairs selected ~25% of sessions | Detect seed bias |
| Shadow chair divergence | Sample 5 sessions; manually compare actual vs simulated shadows | Quantify chair sensitivity (post-hoc, after ≥50 sessions for analytical value) |
| DRIFTJudge false-positive rate | Operator reviews each FOCUS-triggered escalation | Tune threshold |
| Stage timeout rate | % of stages hitting 90s timeout | If >10%, investigate |
| End-to-end success rate | % sessions reaching Stage 5 without abort | Target ≥90% by session 30 |

Mandatory operator review checkpoints: after sessions 10, 20, 30.

---

## 15. Appendix A — Failure mode catalogue

| Failure | Detection | Response |
|---|---|---|
| Member auth expires | DroppedResult with `auth_error=True` | Abort; prompt operator; no auto-retry |
| Member timeout | `asyncio.TimeoutError` | DROPPED; continue iff ≥3 |
| Anonymizer unreachable | TCP refused | Abort Stage 4; terminate |
| Ollama not running | HTTP 503 | Abort sessions requiring Qwen |
| AceMAD weights overflow | `weights[v] > 1e10` | Cap weight; log; continue (already implemented in §7.5) |
| **Entropy flag triggered** | `n_entropy_flags > 0` post-Stage-4 | Log flag; aggregation proceeds; surface in session summary; operator reviews post-session |
| Transcript write fails | OSError | Retry once; fallback `/tmp/h5r-council-emergency-<ulid>.json` |
| Brier scores all zero | Voters identical q_i | Skip weight update; use prior weights |
| Stage 5 chair unavailable | Chair auth-fail | Re-roll; abort if pool empty |
| FOCUS NaN/inf | Validation | Default 0.0; log |
| K2.6 receives draft context (bug) | CI test fails | Hard build failure |
| Qwen Queue A and B concurrent (bug) | Mutex assertion | Hard build failure |
| Codex returns wrong model | Model-pin assertion | Retry; mark DROPPED if persistent |
| Grok model version change between sessions | Response metadata comparison | Log warning |
| **Kimi adapter receives non-`VerifierInput`** | Pydantic ValidationError | Hard build failure (caught at type-check / test time) |

---

## 16. Appendix B — Reference papers

1. Li, Lin, Xia, Jin. *Rethinking Mixture-of-Agents*. arXiv:2502.00674
2. Bandi, Bandi, Harrasse. *Debate, Deliberate, Decide (D3)*. arXiv:2410.04663
3. Dhuliawala et al. *Chain-of-Verification*. arXiv:2309.11495
4. Liu, Zhang, Wu et al. *Breaking the Martingale Curse (AceMAD)*. arXiv:2603.06801
5. Kaesberg, Becker et al. *Stay Focused: Problem Drift*. arXiv:2502.19559
6. Verga et al. *Replacing Judges with Juries (PoLL)*. arXiv:2404.18796
7. Du et al. *Improving Factuality and Reasoning Through Multiagent Debate*. arXiv:2305.14325
8. Chan et al. *ChatEval*. arXiv:2308.07201
9. Zheng et al. *Judging LLM-as-a-Judge*. arXiv:2306.05685

---

## End of specification v2.2

Supersedes v2.1. v2.1 retained at `docs/archive/council_spec_v2.1.md`. Material changes require v2.3 increment and operator sign-off.

The companion file `orchestrator/tests/test_cove_isolation.py` is the locked CI safety net for invariant #2/#7 and Stage 3. It must pass on every commit. See standalone artifact.
