# Typed LLM Council (v2.3.0)

> A multi-model deliberation orchestrator with **type-level verifier isolation**, **anti-sycophancy forced verdicts**, and **per-session audit transcripts**. Originally developed at H5 Resources.

![CI](https://github.com/Silberud/typed-llm-council/actions/workflows/ci.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)

---

## TL;DR

A decoupled Python asyncio orchestrator that pits five model identities against each other through a 7-stage deliberation protocol (Self-MoA-Seq drafting → D3 advocate/juror critique → CoVe factored verification → AceMAD peer-prediction voting → PoLL rotating-chair synthesis → FOCUS drift escalation), with one critical structural invariant: the verifier (Kimi K2.6) is shaped at the type system so it **cannot** receive the draft, framing, advocate defence, juror critiques, or any other council content. Only the operator's original prompt and a single factored verification question cross the boundary.

That invariant is enforced three ways — Pydantic schema (`frozen=True, extra="forbid"`), adapter inheritance split (Kimi inherits `VerifierAdapter`, not `ContributingAdapter`, so it has no `ask()` method at all), and a CI test (`tests/test_cove_isolation.py`) with 16 cases including 50-fixture Hypothesis fuzzing.

---

## Status — what's actually in this release

**v2.3.0 ships Phase A + Phase B + Phase E of a 9-phase plan.** Be explicit about that.

| Phase | What | Status |
|---|---|---|
| A | Skeleton, on-disk layout, supervisor, config | ✅ |
| B | All 6 member adapters (Claude / Gemini / GPT / Qwen / Grok-stub / Kimi-verifier) with auth-check + model-pin | ✅ |
| C | Anonymizer service (TCP 7711, RAM-only label map) | ⏳ |
| D | Stages 0, 1, 2, 5 (framing, Self-MoA-Seq, D3 advocate-juror, PoLL synth) | ⏳ |
| E | Stage 3 CoVe verifier + `test_cove_isolation.py` CI gate | ✅ |
| F | Stage 4 AceMAD aggregation + entropy flag | ⏳ |
| G | Stage 6 FOCUS escalation + DRIFTJudge (Qwen Queue B) | ⏳ |
| H | Telemetry (SQLite WAL) + bootstrap | ⏳ |
| I | v1 migration | n/a |

**`council <prompt>` will deliberately exit non-zero** until D/F/G land. What works end-to-end today is **Stage 3 verification**, which has been live-smoked against real Claude + real Kimi (8 decomposed questions → 8 verifier answers → comparator triggers in 128s wallclock).

```
24/24 structural tests pass
 1/1 live Stage 3 integration smoke passes
```

---

## The design hypothesis (what I'd like feedback on)

Three load-bearing claims this design is making. I'd love pushback:

1. **Structural verifier isolation beats prompt-level isolation.** Most CoVe / verifier patterns rely on "we asked the verifier not to look at the draft." This design makes leaking the draft to the verifier a **TypeError**, not a prompt-engineering hope. The `KimiAdapter` literally has no `ask()` method — there is no API surface that would accept a free-form prompt.

2. **Force verdicts; preserve dissent loudly.** Every voice ends with `APPROVE` / `REJECT` / `MODIFY`. The Chairman's synthesis has four labelled subsections, including a *quarantined* `Chairman's independent judgement` that cannot pose as council consensus, plus a `Dissent log` that the synthesis is forbidden from smoothing over.

3. **Confidence calibration with a hard cap.** A `HIGH` verdict requires both member agreement *and* Chairman premise-validation. Chairman reservation about framing caps the verdict at `MEDIUM` regardless of how many voters agree — preventing false-precision endorsements.

---

## Architecture

```
                          ┌──────────────────────────┐
                          │   Chairman (Opus 4.7)    │
                          │   Drafter + Synthesiser  │
                          │   (rotating per session) │
                          └─┬──────────────────────┬─┘
                            │                      │
                  Stage 1   │   Stage 2            │   Stage 4
                  fan-out   │   D3 critique        │   AceMAD aggregation
                            │                      │
   ┌────────────────────────┴──────────────────────┴───────────────────┐
   │                                                                    │
   ▼                                                                    │
 5 Contributing voters (parallel, peer-reviewed anonymously)            │
 ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────┐ │
 │  Claude    │ │  Gemini    │ │  GPT-5.5   │ │  Qwen 3.6  │ │ Grok   │ │
 │  Drafter   │ │  Research. │ │  Architect │ │  Analyst   │ │ Skeptic│ │
 │ Opus 4.7   │ │  3.1-Pro   │ │  via Codex │ │ Ollama loc │ │ STUBBED│ │
 └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────┘ │
                                                                         │
                            ┌────────────────────────┐                   │
                            │  K2.6 VERIFIER (CoVe)  │   <-- Stage 3     │
                            │  non-voting,           │       isolated    │
                            │  receives ONLY         │       (type +     │
                            │  VerifierInput         │        schema +   │
                            └────────────────────────┘        CI gate)
                                       │
                            ┌──────────▼──────────┐
                            │ Session transcript  │
                            │ (per-stage JSON,    │
                            │  audit-grade)       │
                            └─────────────────────┘
```

---

## Quickstart

```bash
git clone https://github.com/Silberud/typed-llm-council
cd typed-llm-council

python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# Auth status across all 6 seats (no live calls)
python3 -m orchestrator.supervisor --status

# Live ping each seat (burns trivial quota; needs CLIs installed)
python3 -m orchestrator.supervisor --status --live

# Structural tests (24 cases, no live calls, runs in ~0.3s)
pytest orchestrator/tests/

# Stage 3 live integration smoke (real Claude + real Kimi; ~2 min)
pytest orchestrator/tests/_live/ -v
```

See [`docs/operator_setup.md`](docs/operator_setup.md) for the credentials each seat needs.

---

## Looking for feedback on

I'd genuinely like opinions on these — open an [Issue](../../issues) tagged `design-feedback` or a [Discussion](../../discussions):

1. **Chairman dual-hat.** Claude is the synthesiser, the framing-checker, and (until the Skeptic seat ships) wears the Skeptic hat in a clearly-flagged Stage 1.5 pass. Is the quarantining of the Chairman view structurally sufficient, or does the dual hat let too much bias bleed into synthesis?

2. **Procedural anonymisation.** Stage 2 anonymisation is persona-prompt-enforced ("do not speculate on authorship; do not reference 'the other AI'"). Should it move to a mechanical guarantee where the Chairman's wrapper never even *passes* authorship metadata to member subprocesses?

3. **The MEDIUM cap.** The Chairman can unilaterally cap a verdict at MEDIUM by signalling reservation about framing. Appropriate Chairman power, or should it require explicit second confirmation (e.g., dissent from at least one voice)?

4. **Forcing one model to be the verifier.** Kimi K2.6 sits in the verifier seat; if K2.6 has a systematic blind spot, the entire CoVe stage inherits it. Is verifier-rotation worth the complexity, or does single-model verification with strong factored decomposition cover enough?

5. **AceMAD's discrete sample-space scaling.** The original AceMAD paper benchmarks 4–10 verdict outcomes. This design uses a 12-outcome peer-prediction sample space (4 other voters × 3 verdicts; 9 with Grok stubbed). The submartingale-drift property is theoretically robust, but empirically untested at this dimension — what's a sensible empirical bar to validate it on?

---

## Documented deviations from the spec (caught during the build)

| What | Where | Fix |
|---|---|---|
| Claude model id `opus-4-7` | spec | actual full name `claude-opus-4-7` |
| Gemini model id `gemini-3.1-pro` | spec | needs `-preview` suffix until GA |
| Codex subcommand `codex chat` | spec | actual is `codex exec` |
| Gemini CLI `--prompt-file` | spec | doesn't exist; use `-p` + `--skip-trust` |
| Kimi `temperature` param | spec | K2.6 enforces `1` server-side; omit field entirely |
| Codex 0.132 model-pin assertion | spec §9.2 | CLI doesn't emit model in events; adapter warns rather than asserts |

See [`docs/design_notes.md`](docs/design_notes.md) and [`docs/operator_setup.md`](docs/operator_setup.md) for the rest.

---

## Roadmap

Next phases in priority order:

1. **Phase D** — Stages 0/1/2/5. Unlocks end-to-end `council <prompt>` deliberation.
2. **Phase F** — Stage 4 AceMAD with parameterised outcome space (9 while Grok is stubbed; restores 12 when xAI opens an OAuth path on X Premium+).
3. **Phase C** — Anonymizer service (TCP `127.0.0.1:7711`, RAM-only label map).
4. **Phase H** — SQLite WAL telemetry + `council-eval --bootstrap`.
5. **Phase G** — FOCUS drift escalation + DRIFTJudge (Qwen Queue B mutex already built into `qwen.py`).

---

## Citations (status: as-published in the spec)

The design draws on `Self-MoA-Seq`, `D3 advocate-juror`, `CoVe`, `AceMAD`, `FOCUS`, `PoLL` — full reference list in [`docs/council_spec_v2.2.md`](docs/council_spec_v2.2.md) §16. See [`docs/design_notes.md`](docs/design_notes.md) for a note on citation status.

---

## Acknowledgements

Originally developed at **H5 Resources**, where the v1 council (Claude + Gemini + Qwen + Codex) was used internally. The v2.3 rewrite (this repo) was scaffolded with **Claude Code** (Opus 4.7) over a single planning + build session, including the live integration smoke against real Claude and real Kimi. The `test_cove_isolation.py` CI gate is the original work of the H5R operator and is the load-bearing safety net for the verifier-isolation design.

---

## License

[MIT](LICENSE) — © 2026 Igor Silberud
