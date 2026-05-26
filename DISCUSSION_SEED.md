# Seed Discussion post (first-person, to be posted after repo creation)

**Title:** Typed-isolation LLM Council: looking for design feedback on verifier isolation

**Category:** Show and tell (or "Design feedback" if a custom category gets created)

**Body:**

I just open-sourced **Typed LLM Council** — a multi-model deliberation
orchestrator I've been using internally at H5 Resources. Reworked into a
decoupled Python asyncio orchestrator with one specific design choice
I'd like pushback on.

**The structural claim, in three layers:** instead of asking the CoVe
verifier "please do not look at the draft" in its persona prompt:

- **Layer 1 (schema):** `VerifierInput` is a frozen Pydantic model with
  `extra="forbid"`. Any field other than `operator_prompt` +
  `verification_question` is a `ValidationError` at construction.
- **Layer 2 (adapter):** `KimiAdapter` inherits `VerifierAdapter`, not
  `ContributingAdapter`. It has no `ask(prompt)` method at all — calling
  `kimi.ask("…")` raises `AttributeError`, not a slightly weird answer.
- **Layer 3 (content):** between the decomposer and the verifier, a leak
  filter checks every question for n-gram windows from the draft/framing
  and for council-meta role markers ("advocate", "juror", "draft says",
  …) not present in the operator's original prompt. **Fails closed.**
  Added in the 2026-05-25 hardening pass after adversarial review caught
  that schema+adapter alone don't constrain the *content* of the allowed
  `verification_question` field.

All three layers are needed; none is sufficient alone. CI gates:
`tests/test_cove_isolation.py` (16 cases inc. 50-fixture Hypothesis fuzz
on layers 1+2) and `tests/test_leak_filter.py` (12 cases inc. a regression
that patches `decompose_draft` to return a leaky question and asserts
Stage 3 aborts before Kimi sees it).

The release ships **Phase A + Phase B + Phase E (E.0 / E.1 / E.2 opt-in)**
— full disclosure. That gets you the orchestrator skeleton, six adapter
interfaces (Claude / Gemini / GPT / Qwen contributing + Grok-stub +
Kimi-verifier), and Stage 3 verification with three-layer isolation.
Phase E.2 adds a Claude-driven batched CoVe comparator behind
`[stages.stage3] comparator_mode = "real"`; the default remains the
confidence-threshold placeholder until more live validation accumulates.
Stages 0/1/2/4/5/6 are sketched in the spec and detailed in `ROADMAP.md`
but not implemented yet.

What I'd love specific feedback on:

1. **Chairman dual-hat.** Until the Skeptic seat ships (Grok — currently
   stubbed because no subscription-OAuth path exists for X Premium+),
   Claude wears the Skeptic hat in a flagged Stage 1.5 pass. Is
   quarantining the Chairman view structurally enough, or does the dual
   hat let too much bias bleed into synthesis?

2. **Procedural vs mechanical anonymisation.** Stage 2 peer review
   anonymises members as A/B/C by Chairman discipline. Should it move to
   a mechanical guarantee where the wrapper never *passes* authorship
   metadata to member subprocesses?

3. **The MEDIUM cap.** The Chairman can unilaterally cap a verdict at
   MEDIUM by signalling reservation about framing. Appropriate Chairman
   power, or should it require explicit second confirmation from at
   least one voter?

4. **Single-model verifier risk.** Kimi K2.6 sits in the verifier seat.
   If K2.6 has a systematic blind spot, the entire CoVe stage inherits
   it. Verifier rotation worth the complexity, or does single-model
   verification with strong factored decomposition cover enough?

5. **AceMAD discrete sample-space.** The original paper benchmarks 4–10
   verdict outcomes. This design uses a 12-outcome peer-prediction sample
   space (9 with Grok stubbed). What's a sensible empirical bar to
   validate the submartingale-drift property at this dimension?

Repo: https://github.com/Silberud/typed-llm-council
Spec: [`docs/internal_spec_v2.2.md`](https://github.com/Silberud/typed-llm-council/blob/main/docs/internal_spec_v2.2.md) (historical implementation directive — see disclaimer at top)
Design notes: [`docs/design_notes.md`](https://github.com/Silberud/typed-llm-council/blob/main/docs/design_notes.md)
CI gates: [`tests/test_cove_isolation.py`](https://github.com/Silberud/typed-llm-council/blob/main/orchestrator/tests/test_cove_isolation.py) (layers 1+2) and [`tests/test_leak_filter.py`](https://github.com/Silberud/typed-llm-council/blob/main/orchestrator/tests/test_leak_filter.py) (layer 3)

Pile on.

— Igor
