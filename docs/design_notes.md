# Design notes

## Citation status

The implementation specification at `docs/council_spec_v2.2.md` references
several recent papers in §16:

1. Self-MoA-Seq — Li, Lin, Xia, Jin (arXiv 2502.00674)
2. D3 Advocate-Juror — Bandi, Bandi, Harrasse (arXiv 2410.04663)
3. CoVe — Dhuliawala et al. (arXiv 2309.11495)
4. AceMAD — Liu, Zhang, Wu et al. (arXiv 2603.06801)
5. FOCUS — Kaesberg, Becker et al. (arXiv 2502.19559)
6. PoLL — Verga et al. (arXiv 2404.18796)
7. Multi-agent debate — Du et al. (arXiv 2305.14325)
8. ChatEval — Chan et al. (arXiv 2308.07201)
9. Judging LLM-as-a-Judge — Zheng et al. (arXiv 2306.05685)

These references are reproduced from the spec as supplied by the H5R
operator. Refs 3, 6, 7, 8, 9 are well-known prior work in the LLM-judging
literature. Refs 1, 2, 4, 5 carry forward-looking dates (Feb 2025 onward);
if a reference is unverifiable for you, treat the design idea as the
authoritative source rather than the citation.

## Why structural isolation rather than prompt-level

The CoVe Verifier seat could plausibly be implemented with the same
adapter class as the contributing voters, with a "do not look at the
draft" persona prompt enforcing isolation. The choice to put it in a
*different* base class (`VerifierAdapter` vs `ContributingAdapter`), so
that `KimiAdapter` literally has no `ask(prompt)` method, was made because:

- Persona-prompt isolation degrades silently. If a future contributor
  refactors the adapter and accidentally passes the draft to the verifier,
  no test fails — the model just sees the draft and behaves slightly
  differently. There is no audit trail.
- Type-level isolation fails loudly. The same refactor produces a
  `TypeError` at adapter-build time or a `ValidationError` at
  `VerifierInput` construction. The CI gate (`test_cove_isolation.py`)
  asserts both structural facts (no `.ask()` method; `ask_verifier` typed
  with `VerifierInput`) and behavioural facts (no draft / framing /
  persona content reaches Kimi prompts) including 50-fixture
  Hypothesis fuzzing.

## Why force verdicts

LLM-as-judge research (Zheng et al., 2023) and the operator's manual
Claude↔Grok↔ChatGPT iteration showed that without a forced verdict, models
hedge — describing trade-offs rather than picking one. That throws the
synthesis work onto the operator, defeating the point. Every voice's
persona prompt requires an `APPROVE` / `REJECT` / `MODIFY` line, and the
adapter's `extract_verdict()` parses the last such token. A response
without a verdict is treated as a failed turn.

## Why a quarantined Chairman view

The synthesiser is the most powerful seat in any multi-agent deliberation
— it picks what to keep. If the Chairman's own opinion bleeds into the
"council consensus" section, the system has a single-point bias that's
invisible to downstream readers. The protocol's Stage 3 has four labelled
subsections; `Chairman's independent judgement` is its own block, capped
at ~1 paragraph, and the synthesis is forbidden from referencing it as
"council consensus."

The interim Stage 1.5 Chairman Skeptic pass is a related concession: as
long as the Skeptic seat is stubbed (`docs/operator_setup.md` → CG-001),
the Chairman wears that hat too, in a clearly-flagged adversarial pass
that is *not* synthesis. When the Skeptic seat ships, Stage 1.5 is
explicitly scheduled for removal.

## Why anti-sycophancy in the persona prompts

Every persona prompt forbids "great question", compliments, apologies, and
filler. The discipline is borrowed from an internal H5R style ("CBPO
filter") used in branding review — the rule is that the model's output is
useful only when it surfaces what's wrong, not when it makes the operator
feel good.
