"""Real CoVe comparator (Phase E.2) — Claude-driven, batched.

For each (verification_question, verifier_answer) pair the comparator judges
whether the answer SUPPORTs, CONTRADICTs, or is NOT_RELATEd to the draft's
implicit claim. The judgment is made by Claude in a SINGLE batched call
covering all N pairs at once (not N separate calls), so the per-Stage-3
cost overhead is one Claude call.

Opt-in via `config.toml`:
    [stages.stage3]
    comparator_mode = "real"   # default: "placeholder"

The placeholder (`compare_answers_placeholder` in stage3_verification.py)
stays as the default until enough live data accumulates to validate real-
comparator behaviour at scale. The dispatch entry point is
`compare_answers` in stage3_verification.py.

Failure mode: if the real comparator's Claude call fails or its output
cannot be parsed, the dispatcher logs a warning and falls back to the
placeholder. A broken comparator must never abort a Stage 3 session.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any
from orchestrator.schemas.claim_judgment import ClaimJudgment
from orchestrator.schemas.stage_output import VerifierAnswer

log = logging.getLogger("llm-council.services.comparator")


_COMPARATOR_PROMPT_TEMPLATE = """\
You are a CoVe (Chain-of-Verification) comparator. You will see:

- A DRAFT answer the council produced.
- A list of factored verification PAIRS. Each pair has a question derived
  from the draft and the verifier's answer to that question.

For each pair, classify the verifier's answer relative to the draft's
implicit claim that the question is checking:

- SUPPORT: the verifier's answer confirms or is consistent with the draft.
- CONTRADICT: the verifier's answer disagrees with or refutes the draft.
- NOT_RELATE: the answer is on a different topic, off-question, or
  insufficient to judge against the draft.

Return ONLY a JSON array, one object per pair, in the SAME ORDER as the
pairs were given. Each object must have:
  - "index": integer (the pair's 0-based index)
  - "judgment": one of "SUPPORT" | "CONTRADICT" | "NOT_RELATE"
  - "rationale": one short sentence (<= 30 words) explaining the judgment

No preamble. No commentary. No markdown fences. Output the JSON array and
NOTHING else.

DRAFT:
{draft}

PAIRS:
{pairs}
"""


def _format_pairs(questions: list[str], answers: list[VerifierAnswer]) -> str:
    lines = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        lines.append(f"[{i}] Q: {q}")
        lines.append(f"    A: {a.answer}")
        lines.append("")
    return "\n".join(lines)


def _strip_markdown_fences(text: str) -> str:
    """Some Claude responses wrap JSON in ```json ... ``` even when asked not to."""
    text = text.strip()
    if text.startswith("```"):
        # Drop opening fence (with optional language tag) and closing fence.
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _parse_judgments(raw_text: str, n_expected: int) -> list[ClaimJudgment]:
    """Parse Claude's JSON array into validated ClaimJudgment objects.

    Returns one ClaimJudgment per pair, in order. Missing or malformed
    entries are filled with a NOT_RELATE judgment + a 'parse_fallback'
    rationale so downstream aggregation has stable shape.
    """
    fallback: list[ClaimJudgment] = [
        ClaimJudgment(question_index=i, judgment="NOT_RELATE",
                      rationale="parse_fallback")
        for i in range(n_expected)
    ]
    cleaned = _strip_markdown_fences(raw_text)
    if not cleaned:
        return fallback
    try:
        arr = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("comparator JSON parse failed; falling back. raw[:200]=%r", cleaned[:200])
        return fallback
    if not isinstance(arr, list):
        log.warning("comparator output is not a JSON array (got %s); falling back", type(arr).__name__)
        return fallback
    out: dict[int, ClaimJudgment] = {}
    for item in arr:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index", -1))
            judgment = item.get("judgment")
            rationale = str(item.get("rationale", "") or "").strip()
            if 0 <= idx < n_expected and judgment in ("SUPPORT", "CONTRADICT", "NOT_RELATE"):
                if not rationale:
                    rationale = "no rationale"
                out[idx] = ClaimJudgment(
                    question_index=idx,
                    judgment=judgment,  # type: ignore[arg-type]
                    rationale=rationale[:600],
                )
        except (ValueError, TypeError):
            continue
    # Merge fallback for any indices Claude didn't return
    result = [out.get(i, fallback[i]) for i in range(n_expected)]
    return result


async def compare_answers_real(
    draft_text: str,
    questions: list[str],
    verifier_answers: list[VerifierAnswer],
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Real CoVe comparator. ONE batched Claude call across all pairs.

    Output shape is compatible with compare_answers_placeholder, plus a
    `judgments` list of ClaimJudgment objects (serialised as dicts) and a
    `comparator_mode` tag set to "real_claude_batched".
    """
    if not questions or not verifier_answers:
        return {
            "agreements": 0, "disagreements": 0, "flagged": [],
            "judgments": [], "comparator_mode": "real_claude_batched",
        }
    if len(questions) != len(verifier_answers):
        raise ValueError(
            f"questions ({len(questions)}) and verifier_answers "
            f"({len(verifier_answers)}) must have the same length"
        )

    # Local import keeps the orchestrator package import-time cheap.
    from orchestrator.adapters.claude import ClaudeAdapter

    prompt = _COMPARATOR_PROMPT_TEMPLATE.format(
        draft=draft_text,
        pairs=_format_pairs(questions, verifier_answers),
    )
    claude = ClaudeAdapter()
    result = await claude.ask(prompt, timeout=timeout)
    raw_text = getattr(result, "text", "") or ""
    judgments = _parse_judgments(raw_text, n_expected=len(questions))

    agreements = sum(1 for j in judgments if j.judgment == "SUPPORT")
    disagreements = sum(1 for j in judgments if j.judgment == "CONTRADICT")
    flagged: list[str] = []
    for j, ans in zip(judgments, verifier_answers):
        if j.judgment == "CONTRADICT":
            flagged.append(f"Q{j.question_index}: {j.rationale} | A: {ans.answer[:120]}")
        elif j.judgment == "NOT_RELATE" and j.rationale != "parse_fallback":
            flagged.append(f"Q{j.question_index} (off-topic): {j.rationale}")

    return {
        "agreements": agreements,
        "disagreements": disagreements,
        "flagged": flagged,
        "judgments": [j.model_dump() for j in judgments],
        "comparator_mode": "real_claude_batched",
    }
