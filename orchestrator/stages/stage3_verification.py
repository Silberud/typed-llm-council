"""Stage 3 — CoVe Factored Verification (K2.6, non-voting).

Spec §6 Stage 3 + invariants #2, #7:
  - The Verifier (Kimi K2.6) receives ONLY operator_prompt + verification_question.
  - It never sees Draft D, framing, advocate defence, juror critiques, persona prompts.
  - Enforced at the schema layer (VerifierInput frozen + extra=forbid) AND at the
    protocol layer (this module — only `VerifierInput(...)` crosses the kimi boundary).
  - CI test `tests/test_cove_isolation.py` proves the invariant on every commit.

Module-level functions `decompose_draft` and `compare_answers` are intentionally
module-level so the CI test can patch them. Both run with full draft/framing
context — neither calls the verifier.
"""
from __future__ import annotations
import asyncio
from typing import Any
from orchestrator.adapters.base import VerifierAdapter
from orchestrator.schemas.verifier_input import VerifierInput
from orchestrator.schemas.stage_output import VerifierAnswer


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


async def compare_answers(
    claims_from_draft: list[str],
    verifier_answers: list[VerifierAnswer],
) -> dict[str, Any]:
    """Compare verifier answers against the draft's implicit claims.

    The comparator (also Opus 4.7, in a real run) has access to draft + answers
    but produces only an agreement/disagreement count and a list of flagged
    items. For Phase E it ships as a confidence-threshold heuristic; full
    Claude-driven comparison is the Phase F upgrade.
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
    return {"agreements": agreements, "disagreements": disagreements, "flagged": flagged}


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

    # 2. Verifier calls — each carries ONLY VerifierInput. Batched in groups of 5,
    #    parallel within batch (spec §6 Stage 3).
    async def _verify_one(q: str) -> VerifierAnswer:
        payload = VerifierInput(
            operator_prompt=prompt,        # operator's question only
            verification_question=q,        # decomposer output only
        )
        return await kimi.ask_verifier(payload)

    answers: list[VerifierAnswer] = []
    for i in range(0, len(questions), 5):
        batch = questions[i:i + 5]
        batch_answers = await asyncio.gather(*[_verify_one(q) for q in batch])
        answers.extend(batch_answers)

    # 3. Comparator (back outside the sandbox; can see draft + answers)
    comparison = await compare_answers(questions, answers)

    return {
        "stage": 3,
        "questions": questions,
        "answers": [a.model_dump() for a in answers],
        "comparison": comparison,
        "triggers_revision": comparison["disagreements"] > 0,
        # Stage 3 GATES revision, not synthesis (invariant #2 — non-voting).
        "non_voting": True,
    }
