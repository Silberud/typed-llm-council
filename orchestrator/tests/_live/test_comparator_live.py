"""Live integration test for the Phase E.2 real CoVe comparator.

Closes the Hermes-Pass-3 residual concern: "Real comparator is
unit-tested with mocked Claude. It is not live-smoked yet."

Strategy — exercise the comparator against a real Claude judge on
**synthetic** (verifier_answer)s. No Kimi calls; we hand-craft answers
that have known SUPPORT / CONTRADICT / NOT_RELATE relationships to a
fixed draft, then assert that the real comparator classifies them
correctly. This validates the comparator without touching Kimi quota.

Skipped from default `pytest orchestrator/tests/` via `norecursedirs`.
Run explicitly:
    pytest orchestrator/tests/_live/test_comparator_live.py -v -s

Cost: ~1 batched Claude call total (the comparator is batched).
"""
import pytest

from orchestrator.schemas.stage_output import VerifierAnswer
from orchestrator.services.comparator import compare_answers_real


# A fixed draft with three concrete, independently-verifiable claims.
DRAFT = (
    "Python 3.12 was released on 3 October 2023. It includes PEP 695 "
    "(the generic-type syntax via the `type` statement) and PEP 698 "
    "(the @override decorator)."
)

QUESTIONS = [
    "Was Python 3.12 released on 3 October 2023?",
    "Was Python 3.12 released in 2024?",
    "What is the capital of France?",
]

# Synthetic verifier answers crafted to have KNOWN relationships to the
# draft. The comparator (Claude) should classify each accordingly.
ANSWERS = [
    VerifierAnswer(
        answer="Yes — Python 3.12 was released on 3 October 2023.",
        confidence=0.95, confidence_parsed=True,
    ),  # SUPPORT: directly confirms the draft's release-date claim
    VerifierAnswer(
        answer="No. Python 3.12 was not released in 2024 — it was released in October 2023.",
        confidence=0.95, confidence_parsed=True,
    ),  # SUPPORT (the answer agrees the draft is right; "no" refers to the question's
        # false premise, not to the draft). This is the realistic CoVe shape.
    VerifierAnswer(
        answer="The capital of France is Paris.",
        confidence=0.99, confidence_parsed=True,
    ),  # NOT_RELATE: answer is off-topic for any draft claim
]


@pytest.mark.asyncio
async def test_real_comparator_classifies_correctly_against_live_claude():
    """Hand-crafted (Q, A) pairs with known semantics; real Claude judges.

    We tolerate some classifier wiggle-room (Claude is non-deterministic):
      - At least the off-topic answer must come back NOT_RELATE.
      - The two on-topic answers must come back SUPPORT (the answers
        agree with the draft; the second is a "no, the question is wrong"
        which still aligns with the draft's claim).
      - No answer in this fixture should come back CONTRADICT.
    """
    result = await compare_answers_real(
        draft_text=DRAFT, questions=QUESTIONS, verifier_answers=ANSWERS,
        timeout=120.0,
    )
    print("\n  comparator_mode:", result["comparator_mode"])
    print("  agreements:", result["agreements"])
    print("  disagreements:", result["disagreements"])
    print("  judgments:")
    for j in result["judgments"]:
        print(f"    [{j['question_index']}] {j['judgment']:11s}  {j['rationale']}")

    # Strict assertion: comparator actually ran (not fallback)
    assert result["comparator_mode"] == "real_claude_batched"
    assert len(result["judgments"]) == 3

    # The off-topic answer (#2) MUST be NOT_RELATE — this is the clearest signal
    judgment_2 = result["judgments"][2]["judgment"]
    assert judgment_2 == "NOT_RELATE", (
        f"Q2 (capital of France vs Python 3.12 draft) should be NOT_RELATE; "
        f"got {judgment_2}. Rationale: {result['judgments'][2]['rationale']!r}"
    )

    # Neither on-topic answer should be CONTRADICT (both confirm the draft)
    for i in (0, 1):
        j = result["judgments"][i]["judgment"]
        assert j != "CONTRADICT", (
            f"Q{i} should NOT be CONTRADICT (answer agrees with draft); "
            f"got {j}. Rationale: {result['judgments'][i]['rationale']!r}"
        )


@pytest.mark.asyncio
async def test_real_comparator_detects_contradiction_against_live_claude():
    """Same draft, but a synthetic answer that explicitly contradicts it.
    Claude should flag this as CONTRADICT."""
    contradiction_q = "Did Python 3.12 include PEP 695?"
    contradiction_a = VerifierAnswer(
        answer="No, PEP 695 was not in Python 3.12. It was added later in 3.14.",
        confidence=0.85, confidence_parsed=True,
    )
    result = await compare_answers_real(
        draft_text=DRAFT,
        questions=[contradiction_q],
        verifier_answers=[contradiction_a],
        timeout=120.0,
    )
    print("\n  comparator_mode:", result["comparator_mode"])
    print("  judgment:", result["judgments"][0])

    assert result["comparator_mode"] == "real_claude_batched"
    assert result["judgments"][0]["judgment"] == "CONTRADICT", (
        f"Synthetic answer 'PEP 695 was not in Python 3.12' contradicts the "
        f"draft's claim that 3.12 includes PEP 695. Expected CONTRADICT; "
        f"got {result['judgments'][0]['judgment']!r}. "
        f"Rationale: {result['judgments'][0]['rationale']!r}"
    )
    assert result["disagreements"] >= 1
