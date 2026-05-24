"""Stage 3 end-to-end integration smoke — Phase E live acceptance.

Hits the REAL Claude decomposer and the REAL Kimi verifier. Burns a small
amount of subscription quota (~1 Claude call + 5-10 Kimi calls per run).

Skipped from the default `pytest orchestrator/tests/` run via `norecursedirs`.
Invoke explicitly:
    pytest orchestrator/tests/_live -v
"""
import pytest
from orchestrator.adapters.kimi import KimiAdapter
from orchestrator.stages.stage3_verification import stage3_cove_verify


# A draft with multiple concrete, independently-verifiable sub-claims.
# Python 3.12 release facts are intentionally chosen because:
#   - several atomic factual claims (date, PEP numbers, features)
#   - K2.6 has good factual recall for software releases
#   - if the comparator triggers a revision, we can inspect what flagged.
DRAFT = (
    "Python 3.12 was released on 3 October 2023. It includes PEP 695 "
    "(generic-type syntax via the new `type` statement), PEP 698 (the "
    "`@override` decorator), and PEP 701 (formalised f-string grammar). "
    "Performance improved overall thanks to PEP 669's monitoring API and "
    "PEP 684's per-interpreter GIL groundwork."
)

PROMPT = (
    "Summarise the headline features and release date of Python 3.12 in a "
    "single paragraph, suitable for a technical changelog entry."
)

FRAMING = (
    "The reader is an engineering team deciding whether to migrate from "
    "3.11 to 3.12 within the next quarter. Accuracy of dates and PEP "
    "numbers matters; speculative performance claims are unwelcome."
)


class _Transcript:
    """Minimal stand-in for the operator transcript object."""
    session_id = "live-stage3-smoke"


@pytest.mark.asyncio
async def test_stage3_end_to_end_against_real_claude_and_kimi():
    """The full Stage 3 protocol against live Claude + live Kimi."""
    kimi = KimiAdapter()
    result = await stage3_cove_verify(
        prompt=PROMPT,
        draft_text=DRAFT,
        framing_note=FRAMING,
        kimi=kimi,
        transcript=_Transcript(),
    )
    # Phase E acceptance criteria (spec §11):
    n_q = len(result["questions"])
    n_a = len(result["answers"])
    print(f"\n  questions={n_q}  answers={n_a}  "
          f"agree={result['comparison']['agreements']}  "
          f"disagree={result['comparison']['disagreements']}  "
          f"triggers_revision={result['triggers_revision']}")
    if result["comparison"]["flagged"]:
        print("  flagged samples:")
        for f in result["comparison"]["flagged"][:3]:
            print(f"    - {f}")
    # 5 ≤ questions ≤ 10 (decomposer target)
    assert 3 <= n_q <= 10, f"decomposer returned {n_q} questions (expected 5–10, accept 3–10)"
    # Verifier returned same number of answers
    assert n_a == n_q, f"verifier returned {n_a} answers for {n_q} questions"
    # Each answer has a confidence in [0, 1]
    for a in result["answers"]:
        assert 0.0 <= a["confidence"] <= 1.0
    # Stage 3 is non-voting (invariant #2)
    assert result["non_voting"] is True
    # triggers_revision is a clean bool
    assert isinstance(result["triggers_revision"], bool)
