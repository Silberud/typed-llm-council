# Typed LLM Council (v2.3.0)

> A multi-model deliberation orchestrator with **three-layer verifier isolation** (schema + adapter + content), **anti-sycophancy forced verdicts**, and **structured per-stage outputs**. Developed by Igor Silberud (H5 Resources).

![CI](https://github.com/Silberud/typed-llm-council/actions/workflows/ci.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)

> Not affiliated with or endorsed by Anthropic, Google, OpenAI, Alibaba/Qwen, xAI, or Moonshot. All model providers are referenced by their public CLI/API names. No telemetry is sent anywhere by this code — everything is local.

---

## TL;DR

This repo is **building toward** a multi-model council orchestrator with a 7-stage deliberation protocol (Self-MoA-Seq drafting → D3 advocate/juror critique → CoVe factored verification → AceMAD peer-prediction voting → PoLL rotating-chair synthesis → FOCUS drift escalation). The **current release ships the adapter skeleton + a hardened Stage 3 (CoVe verifier-isolation) path**; the rest of the pipeline is sketched in the spec but not yet implemented — see the status table below and [`ROADMAP.md`](ROADMAP.md).

The architecturally distinct claim of *what is currently implemented* is **structural adapter-level isolation between voting and verifying seats**, enforced at three independent layers:

1. **Schema layer** — `VerifierInput` is `frozen=True, extra="forbid"`. Any field other than `operator_prompt` + `verification_question` is a `ValidationError`.
2. **Adapter layer** — `KimiAdapter` inherits `VerifierAdapter`, not `ContributingAdapter`. It has no `ask()` method at all — calling `kimi.ask("…")` raises `AttributeError`, not a slightly weird answer.
3. **Content layer** — between `decompose_draft()` and `kimi.ask_verifier()`, a leak filter (`services/leak_filter.py`) checks every verification question for n-gram windows from the draft/framing and for council-meta role marker phrases ("the advocate", "council concluded", "the draft", …) not present in the operator's original prompt. **Fails closed on detectable verbatim and procedural leakage.** This is a heuristic content-layer filter — not formal semantic noninterference. Paraphrastic leakage (a decomposer that rewords draft claims in its own words) can still pass; the boundary it closes is the *verbatim* and *role-meta* channels, not all of semantics. That is acceptable in practice because CoVe questions necessarily contain claim restatements; the filter is calibrated to allow short restatements while blocking longer drafter prose.

Layers 1 and 2 are structural (Phase E.0). Layer 3 was added in the 2026-05-25 hardening pass (Phase E.1) after an adversarial review caught that schema+adapter alone don't constrain the *content* of the allowed field. **All three layers are needed; none is sufficient alone.** This is honestly stronger than the original CoVe paper's property (which doesn't isolate the verifier from "draft-derived" content at all — questions in CoVe normally do contain claim restatements).

Verified by `tests/test_cove_isolation.py` (16 cases, 50-fixture Hypothesis fuzz on layers 1+2) and `tests/test_leak_filter.py` (12 cases including a regression test that patches `decompose_draft` to return a leaky question and asserts Stage 3 aborts before Kimi sees it).

---

## Status — what's actually in this release

**v2.3.0 ships Phase A + Phase B + Phase E (E.0 + E.1 + E.2 opt-in) of a 9-phase plan.** Be explicit about that.

| Phase | What | Status |
|---|---|---|
| A | Skeleton, on-disk layout, supervisor, config loader | ✅ |
| B | Six adapters: five contributing interfaces (Claude / Gemini / GPT / Qwen / Grok-stub) + one verifier (Kimi). Grok is a documented stub; Kimi is non-voting | ✅ |
| C | Anonymizer service (TCP 7711, RAM-only label map) | ⏳ |
| D | Stages 0, 1, 2, 5 (framing, Self-MoA-Seq, D3 advocate-juror, PoLL synth) | ⏳ |
| **E.0** | Stage 3 structural isolation (schema + adapter layers) | ✅ |
| **E.1** | Stage 3 content-layer leak filter + regression tests | ✅ |
| **E.2** | Real CoVe comparator — Claude-driven, batched (1 call/session) | ✅ unit-tested + **live-validated** against real Claude (SUPPORT / CONTRADICT / NOT_RELATE all classify correctly on hand-crafted cases); opt-in via `[stages.stage3] comparator_mode = "real"` |
| F | Stage 4 AceMAD aggregation + entropy flag | ⏳ |
| G | Stage 6 FOCUS escalation + DRIFTJudge (Qwen Queue B) | ⏳ |
| H | Persistent transcripts + SQLite WAL telemetry + bootstrap | ⏳ |
| I | v1 migration | n/a |

**`council <prompt>` will deliberately exit non-zero** until D/F/G land. What works end-to-end today is **Stage 3 verification with three-layer isolation**, live-smoked against real Claude + real Kimi (7–8 decomposed questions → all pass the leak filter → 7–8 verifier answers in ~2–4 min wallclock).

```
55/55 structural tests pass
   (16 cove-isolation + 16 leak-filter + 13 comparator + 10 adapter-smoke)
 1/1 live Stage 3 integration smoke passes (real Claude + real Kimi)
 2/2 live comparator tests pass (real Claude judging synthetic answers)
```

**Deferred phases — each has a tracking Issue you can claim:**

| Phase | Issue | Title | Status |
|---|---|---|---|
| C | [#2](https://github.com/Silberud/typed-llm-council/issues/2) | Anonymizer service (TCP 127.0.0.1:7711) | open |
| D | [#3](https://github.com/Silberud/typed-llm-council/issues/3) | Stages 0/1/2/5 (end-to-end council) | open, blocked by #2 |
| F | [#4](https://github.com/Silberud/typed-llm-council/issues/4) | Stage 4 AceMAD aggregation | open, blocked by #3 |
| G | [#5](https://github.com/Silberud/typed-llm-council/issues/5) | Stage 6 FOCUS + DRIFTJudge | open, blocked by #3, #4 |
| H | [#6](https://github.com/Silberud/typed-llm-council/issues/6) | Telemetry + bootstrap | open, blocked by #3 |

See [`ROADMAP.md`](ROADMAP.md) for per-phase scope, files, dependencies, and effort estimates. This is a personal project; Phase D is the next milestone the maintainer plans to land. Contributors welcome (see [`CONTRIBUTING.md`](CONTRIBUTING.md)).

**Adversarial review trail:** Hermes Agent (GPT-5.5) reviewed the repository across multiple passes from 24–26 May 2026. Pass 1 raised 20 numbered findings against the initial private-staging release; subsequent hardening passes closed 19/20 and addressed the remaining framing caveat with runtime checks and more precise language. Later passes cleaned public-facing docs, validated the real E.2 comparator against live Claude on synthetic SUPPORT / CONTRADICT / NOT_RELATE cases, and corrected launch metadata. Per-finding status: [`docs/hermes_findings_status.md`](docs/hermes_findings_status.md). The review trail is preserved as part of the design-feedback story, not as a substitute for independent human review.

---

## The design hypothesis (what I'd like feedback on)

Three load-bearing claims this design is making. I'd love pushback:

1. **Three-layer verifier isolation beats prompt-level isolation alone.** Most CoVe / verifier patterns rely on "we asked the verifier not to look at the draft" — a prompt-engineering promise. This design adds two structural enforcements (schema-level extra-field rejection; adapter-level absence of an `ask()` method on Kimi) plus a content-level n-gram + role-marker leak filter between decomposer and verifier. The claim isn't that any one layer is novel; it's that combining all three makes accidental leakage by future contributors *fail loudly* instead of silently degrading the verifier's independence.

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
                            │  non-voting,           │       three-layer │
                            │  receives ONLY         │       isolation:  │
                            │  VerifierInput AFTER   │       schema +    │
                            │  leak filter           │       adapter +   │
                            └────────────────────────┘       content
                                       │
                            ┌──────────▼──────────┐
                            │ Per-stage outputs   │
                            │ (structured;        │
                            │  persistence is     │
                            │  Phase H)           │
                            └─────────────────────┘
```

---

## Quickstart

Requires **Python 3.11+**. On macOS, bare `python3` may still resolve to 3.9 even on recent systems — use `python3.11` or `python3.12` (or `uv venv --python 3.12`) explicitly:

```bash
git clone https://github.com/Silberud/typed-llm-council
cd typed-llm-council

# Use python3.11 or python3.12 explicitly — NOT bare python3 (may be 3.9 on macOS)
python3.12 -m venv .venv && . .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel  # older pip can fail editable installs
pip install -e ".[dev]"

# Auth status across all 6 seats (no live calls)
python -m orchestrator.supervisor --status

# Live ping each seat (burns trivial quota; needs the model CLIs installed)
python -m orchestrator.supervisor --status --live

# Structural tests (55 tests, no live calls)
pytest orchestrator/tests/

# Stage 3 live integration smoke (real Claude + real Kimi; ~2 min)
pytest orchestrator/tests/_live/ -v
```

See [`docs/operator_setup.md`](docs/operator_setup.md) for the credentials each seat needs.

---

## Looking for feedback on

I'd genuinely like opinions on these — open an [Issue](../../issues) tagged `design-feedback` or a [Discussion](../../discussions):

1. **Chairman dual-hat.** Claude is the synthesiser, the framing-checker, and (until the Skeptic seat ships) wears the Skeptic hat in a clearly-flagged Stage 1.5 pass. Is the quarantining of the Chairman view structurally sufficient, or does the dual hat let too much bias bleed into synthesis?

2. **Procedural vs mechanical anonymisation.** Stage 2 anonymisation is persona-prompt-enforced ("do not speculate on authorship; do not reference 'the other AI'"). Should it move to a mechanical guarantee where the Chairman's wrapper never even *passes* authorship metadata to member subprocesses?

3. **The MEDIUM cap.** The Chairman can unilaterally cap a verdict at MEDIUM by signalling reservation about framing. Appropriate Chairman power, or should it require explicit second confirmation (e.g., dissent from at least one voice)?

4. **Single-model verifier risk.** Kimi K2.6 sits in the verifier seat; if K2.6 has a systematic blind spot, the entire CoVe stage inherits it. Is verifier-rotation worth the complexity, or does single-model verification with strong factored decomposition cover enough?

5. **AceMAD's discrete sample-space scaling.** The original AceMAD paper benchmarks 4–10 verdict outcomes. This design uses a 12-outcome peer-prediction sample space (4 other voters × 3 verdicts; 9 with Grok stubbed). The submartingale-drift property is theoretically robust, but empirically untested at this dimension — what's a sensible empirical bar to validate it on?

---

## Model compatibility matrix

| Seat | Configured model id | Test status |
|---|---|---|
| Claude (Drafter/Chair) | `claude-opus-4-7` | live-tested 2026-05-24 via Claude Code CLI |
| Gemini (Researcher) | `gemini-3.1-pro-preview` | code path live-tested; OAuth account was quota-throttled (TRANS-001) — adapter wiring is correct, full live confirmation pending |
| GPT (Architect) | `gpt-5.5` | live-tested 2026-05-24 via Codex CLI 0.132.0 (model-pin degraded — see CG-002) |
| Qwen (Analyst) | `qwen3.6:35b-a3b-coding-nvfp4` | live-tested 2026-05-24 (local Ollama, M3 Max) |
| Grok (Skeptic) | stubbed | n/a — see CG-001 |
| Kimi (Verifier) | `kimi-k2.6` | live-tested 2026-05-24 via `api.moonshot.ai` (API-key path per EX-001) |

Model ids reflect what was current and tested at the date shown. If you're reading this much later, expect drift; pin via `config.toml` or env vars (`LLM_COUNCIL_CONFIG`).

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

## Project conventions

How the repository operates day-to-day:

| File | What it covers |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Plan-then-PR workflow, load-bearing files to read first, test/live-test rules |
| [`docs/plans/TEMPLATE.md`](docs/plans/TEMPLATE.md) | Forensic plan-doc structure (audit-evidence → tasks → success criteria) — used by every non-trivial PR |
| [`SECURITY.md`](SECURITY.md) | Private vulnerability-disclosure policy + secret-handling expectations |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Contributor Covenant 2.1, with project-specific note on critiquing model behaviour |
| [`CITATION.cff`](CITATION.cff) | Machine-readable citation metadata (`Cite this repository` widget on GitHub) |
| [`docs/release_process.md`](docs/release_process.md) | Versioning policy, pre-flight checklist, release-cut commands |
| [`CHANGELOG.md`](CHANGELOG.md) | Per-version commit-by-commit history |

Issue templates (`.github/ISSUE_TEMPLATE/`) ask for the structured details bug reports / phase proposals / design-feedback responses should carry. A PR template (`.github/pull_request_template.md`) reminds contributors to link the plan doc and tick the quality gates.

---

## Citations

The design draws on `Self-MoA-Seq`, `D3 advocate-juror`, `CoVe`, `AceMAD`, `FOCUS`, `PoLL` — full reference list in [`docs/internal_spec_v2.2.md`](docs/internal_spec_v2.2.md) §16. Refs to long-established prior work (CoVe, PoLL, Multi-agent Debate, ChatEval, LLM-as-Judge) are well-known; refs to more recent or forward-looking work carry the spec's own provenance — see [`docs/design_notes.md`](docs/design_notes.md) for the citation note.

---

## Acknowledgements

Developed by **Igor Silberud** (H5 Resources is the maintainer's own operating entity; no third-party employer rights are implicated). The v1 council that preceded this rewrite (Claude + Gemini + Qwen + Codex) was used internally at H5 Resources.

AI development tools, including **Claude Code (Opus 4.7)**, were used during implementation of the v2.3 rewrite; all code is reviewed and licensed by the maintainer, and the design hypothesis is the maintainer's own. No provider endorsement is implied. The `test_cove_isolation.py` CI gate is original work by the maintainer and is the load-bearing safety net for layers 1 and 2 of the verifier-isolation design; the leak filter in `services/leak_filter.py` and the regression tests in `test_leak_filter.py` were added in the 2026-05-25 hardening pass after adversarial review caught that schema+adapter alone don't constrain the content of the allowed field.

---

## License

[MIT](LICENSE) — © 2026 Igor Silberud
