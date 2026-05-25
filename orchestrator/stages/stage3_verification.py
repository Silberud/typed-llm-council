"""Stage 3 — CoVe Factored Verification (K2.6, non-voting).

Spec §6 Stage 3 + invariants #2, #7. Isolation is enforced at three layers
— and ALL THREE are needed; none is sufficient alone:

  1. Schema layer  — VerifierInput is frozen + extra='forbid' (any field
     other than operator_prompt + verification_question is a ValidationError).
  2. Adapter layer — KimiAdapter inherits VerifierAdapter (not Contributing-
     Adapter) and has no `ask()` method at all.
  3. Content layer — `services.leak_filter.check_inputs_clean` runs between
     `decompose_draft()` and `kimi.ask_verifier()` and fails closed when a
     question contains forbidden n-gram windows from draft/framing or
     council-meta role markers not present in the operator's original prompt.

Layers 1 and 2 are structural (Tier 1). Layer 3 (added in the 2026-05-25
hardening pass) closes the content channel that schemas can't reach: a leaky
decomposer could put draft text inside the allowed `verification_question`
field. See `orchestrator/services/leak_filter.py`.

Module-level functions `decompose_draft` and `compare_answers_placeholder`
are intentionally module-level so the CI test can patch them. Both run
with full draft/framing context — neither calls the verifier.
"""
from __future__ import annotations
import asyncio
from typing import Any
from orchestrator.adapters.base import VerifierAdapter
from orchestrator.schemas.verifier_input import VerifierInput
from orchestrator.schemas.stage_output import VerifierAnswer
from orchestrator.services.leak_filter import (
    LeakDetectedError, check_inputs_clean,
)


async def decompose_draft(prompt: str, draft_text: str, framing_note: str) -> list[str]:
    """Decompose Draft D into 5–10 atomic, independently-verifiable questions.

    Runs on Opus 4.7 (Claude Code CLI) as the decomposer. Has full access to
    draft + framing because it lives OUTSIDE the verifier sandbox. Its output
    (questions only) is what the verifier later sees inside VerifierInput —
    the decomposer is responsible for not echoing draft text verbatim.
    """
    # Local import to avoid a circular dependency at orchestrator import time.
    from orchestrator.adapters.claude import ClaudeAdapter

    decomposer_prompt = (
        "You are the CoVe decomposer. Given the operator's original question, "
        "the framing note, and the draft answer, decompose the draft into 5 to "
        "10 ATOMIC, INDEPENDENTLY-VERIFIABLE factual questions. Each question "
        "must be answerable on its own facts, without reference to the draft's "
        "reasoning or wording. Do NOT echo draft sentences verbatim.\n\n"
        f"Operator prompt:\n{prompt}\n\n"
        f"Framing note:\n{framing_note}\n\n"
        f"Draft:\n{draft_text}\n\n"
        "Return one question per line. No numbering. No preamble. No commentary."
    )
    claude = ClaudeAdapter()
    # Single source of truth for stage-3 timeout: session.default_stage_timeout
    # in config.toml (defaults to 90s). Read lazily to avoid circular import.
    from orchestrator.supervisor import load_config
    timeout = float(load_config().get("session", {}).get("default_stage_timeout", 90))
    # Decomposer is slower than verifier calls (longer context) — give it 1.5×.
    result = await claude.ask(decomposer_prompt, timeout=timeout * 1.5)
    text = getattr(result, "text", "") or ""
    lines = [ln.strip().lstrip("- ").lstrip("0123456789.) ").strip()
             for ln in text.splitlines() if ln.strip()]
    return lines[:10]


async def compare_answers_placeholder(
    questions: list[str],
    verifier_answers: list[VerifierAnswer],
) -> dict[str, Any]:
    """PLACEHOLDER — Phase E.2 will replace this with a real CoVe comparator.

    What this function does TODAY:
      - Counts answers with confidence ≥ 0.5 as "agreements" and the rest as
        "disagreements". The `questions` parameter is currently unused.
      - This is a confidence-threshold heuristic, NOT a comparison of draft
        claims against verifier answers. A confident "No, that's false"
        from Kimi is counted as "agreement" because confidence is high.

    What Phase E.2 will do:
      - Call Claude (or another contributor model) as a comparator with the
        draft claims, the verifier's answers, and a strict factual-alignment
        rubric. Return real agreement/disagreement judgments per claim.

    The README's Phase status table reflects this split (E.0 structural
    isolation = done; E.1 leak filter = done; E.2 real comparator = pending).
    """
    agreements = 0
    disagreements = 0
    flagged: list[str] = []
    for ans in verifier_answers:
        if ans.confidence < 0.5:
            disagreements += 1
            flagged.append(ans.answer[:160])
        else:
            agreements += 1
    return {
        "agreements": agreements,
        "disagreements": disagreements,
        "flagged": flagged,
        "comparator_mode": "placeholder_confidence_threshold",
    }


# Back-compat alias for callers that still reference the old name (and
# pytest patches in `test_cove_isolation.py` that target this symbol).
compare_answers = compare_answers_placeholder


async def stage3_cove_verify(
    *,
    prompt: str,
    draft_text: str,
    framing_note: str,
    kimi: VerifierAdapter,
    transcript: Any,
) -> dict[str, Any]:
    """Run Stage 3.

    Returns a dict with the verification report. Any disagreement triggers
    Stage 5 revision (spec §6 Stage 3 final line). Does NOT vote.
    """
    # 1. Decompose (outside the sandbox; has full context)
    questions = await decompose_draft(
        prompt=prompt, draft_text=draft_text, framing_note=framing_note,
    )
    if len(questions) < 3:
        # Spec §11 Phase E target is 5–10; below 3 the decomposer has failed.
        raise RuntimeError(f"decomposer produced too few questions: {len(questions)}")
    questions = questions[:10]

    # 2. LAYER-3 leak filter — fail closed if any question carries draft/
    #    framing content beyond what the operator's prompt already contained.
    #    See `orchestrator/services/leak_filter.py` for rules. This is the
    #    content-channel guard that schema-level isolation cannot reach.
    for q in questions:
        try:
            check_inputs_clean(
                operator_prompt=prompt,
                verification_question=q,
                draft_text=draft_text,
                framing_note=framing_note,
            )
        except LeakDetectedError as e:
            raise RuntimeError(
                f"Stage 3 aborted: decomposer produced a leaky question. {e}"
            ) from e

    # 3. Verifier calls — each carries ONLY VerifierInput. Batched in groups of 5,
    #    parallel within batch (spec §6 Stage 3).
    async def _verify_one(q: str) -> VerifierAnswer:
        payload = VerifierInput(
            operator_prompt=prompt,        # operator's question only
            verification_question=q,        # decomposer output (leak-filtered above)
        )
        return await kimi.ask_verifier(payload)

    answers: list[VerifierAnswer] = []
    for i in range(0, len(questions), 5):
        batch = questions[i:i + 5]
        batch_answers = await asyncio.gather(*[_verify_one(q) for q in batch])
        answers.extend(batch_answers)

    # 4. Comparator (placeholder until Phase E.2; see compare_answers_placeholder docstring)
    comparison = await compare_answers_placeholder(questions, answers)

    return {
        "stage": 3,
        "questions": questions,
        "answers": [a.model_dump() for a in answers],
        "comparison": comparison,
        "triggers_revision": comparison["disagreements"] > 0,
        # Stage 3 GATES revision, not synthesis (invariant #2 — non-voting).
        "non_voting": True,
    }
