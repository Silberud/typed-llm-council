# Seed Discussion post (first-person, to be posted after repo creation)

**Title:** I built a typed-isolation LLM Council — looking for design feedback

**Category:** Show and tell (or "Design feedback" if a custom category gets created)

**Body:**

I just open-sourced **Typed LLM Council** — a multi-model deliberation
orchestrator I've been using internally at H5 Resources. Rewrote it this
month as a decoupled Python asyncio orchestrator with one specific design
choice I'd like pushback on.

**The structural claim:** instead of asking the CoVe verifier "please do
not look at the draft" in its persona prompt, the verifier (Kimi K2.6)
sits behind a `VerifierAdapter` base class that has no `ask(prompt)`
method at all. Its only entry point is `ask_verifier(input: VerifierInput)`,
where `VerifierInput` is a frozen Pydantic model with `extra="forbid"`.
A future contributor who accidentally tries to pass the draft to the
verifier gets a `ValidationError` at construction time, not a slightly
weird answer. CI gate is `tests/test_cove_isolation.py` — 16 cases
including 50-fixture Hypothesis fuzzing.

The release ships **Phase A + Phase B + Phase E only** — full disclosure.
That gets you the orchestrator skeleton, all six adapters (Claude /
Gemini / GPT / Qwen / Grok-stub / Kimi-verifier), and the Stage 3 CoVe
verifier with the locked CI safety net. Stages 0/1/2/4/5/6 are still
sketched as a 7-stage protocol in `docs/council_spec_v2.2.md` but not
implemented.

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
Spec: [`docs/council_spec_v2.2.md`](https://github.com/Silberud/typed-llm-council/blob/main/docs/council_spec_v2.2.md)
Design notes: [`docs/design_notes.md`](https://github.com/Silberud/typed-llm-council/blob/main/docs/design_notes.md)
The locked CI gate: [`tests/test_cove_isolation.py`](https://github.com/Silberud/typed-llm-council/blob/main/orchestrator/tests/test_cove_isolation.py)

Pile on.

— Igor
