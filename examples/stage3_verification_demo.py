"""Structural demo of the Phase E Stage 3 CoVe verifier pipeline.

This runs the orchestrator's `stage3_cove_verify` function end-to-end with:
  - a MOCK decomposer (so no Claude call is made)
  - a MOCK Kimi verifier (so no Moonshot call is made)
  - the REAL `services/leak_filter.py` between them

It exists so a visitor can see the pipeline shape — including the
three-layer isolation enforcement — without spending any model quota.

Run from repo root:
    python3 examples/stage3_verification_demo.py

For a *live* version that uses real Claude + real Kimi, see
`orchestrator/tests/_live/test_stage3_live.py`.
"""
from __future__ import annotations
import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

# Ensure we import the in-tree `orchestrator/` package, not any global editable
# install that might shadow it. Python sets sys.path[0] to the script's directory
# (examples/), so without this the import would resolve elsewhere.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from orchestrator.adapters.kimi import KimiAdapter  # noqa: E402
from orchestrator.schemas.stage_output import VerifierAnswer  # noqa: E402
from orchestrator.schemas.verifier_input import VerifierInput  # noqa: E402
from orchestrator.stages.stage3_verification import stage3_cove_verify  # noqa: E402


# ---- mock data --------------------------------------------------------

OPERATOR_PROMPT = "Summarise the headline features and release date of Python 3.12."

DRAFT = (
    "Python 3.12 was released on 3 October 2023. It includes PEP 695 "
    "(generic-type syntax) and PEP 698 (the @override decorator)."
)

FRAMING_NOTE = "Reader is an engineering team. Accuracy of dates and PEP numbers matters."

# What the decomposer would normally return. The leak filter will see these.
MOCK_QUESTIONS = [
    "Was Python 3.12 released on 3 October 2023?",
    "Does Python 3.12 include PEP 695?",
    "Does Python 3.12 include PEP 698?",
    "Is PEP 695 about generic-type syntax?",
    "Is PEP 698 the @override decorator?",
]

# What the verifier would normally return. Three SUPPORT, two synthetic.
MOCK_ANSWERS = [
    "Yes, Python 3.12 was released on 3 October 2023.",
    "Yes, Python 3.12 introduced PEP 695.",
    "Yes, Python 3.12 introduced PEP 698.",
    "PEP 695 introduces a new type-parameter syntax.",
    "PEP 698 adds the @override decorator for explicit method overriding.",
]


# ---- a Kimi adapter that returns canned answers (no Moonshot call) ----

class MockKimi(KimiAdapter):
    """A KimiAdapter subclass that returns mock VerifierAnswers without
    calling the Moonshot API. Preserves the VerifierAdapter type contract."""

    def __init__(self):
        # Skip parent __init__ so we don't validate endpoint / hit Keychain.
        # We just need to be a VerifierAdapter for the structural contract.
        self.model = "mock-kimi"
        self.endpoint = "mock://localhost"
        self.keychain_service = ""
        self.keychain_account = ""
        self._call_index = 0
        # Map questions -> answers in order so the demo is deterministic.
        self._answers_by_question = dict(zip(MOCK_QUESTIONS, MOCK_ANSWERS))

    async def ask_verifier(self, input: VerifierInput) -> VerifierAnswer:
        # The leak filter has already validated this input by the time we're called.
        # Just look up the canned answer and return it.
        text = self._answers_by_question.get(
            input.verification_question,
            "(no mock answer; synthetic 'I don't know')",
        )
        return VerifierAnswer(
            answer=text,
            confidence=0.9,
            confidence_parsed=True,
            model_used="mock-kimi",
        )


# ---- the demo ----------------------------------------------------------

async def main() -> int:
    print("=" * 70)
    print("Typed LLM Council — Stage 3 (CoVe) structural demo")
    print("=" * 70)
    print(f"\nOperator prompt:\n  {OPERATOR_PROMPT}")
    print(f"\nDraft:\n  {DRAFT}")
    print(f"\nFraming note:\n  {FRAMING_NOTE}")

    print("\n" + "-" * 70)
    print("Mock decomposer would return these verification questions:")
    print("-" * 70)
    for i, q in enumerate(MOCK_QUESTIONS):
        print(f"  [{i}] {q}")

    print("\n" + "-" * 70)
    print("Running stage3_cove_verify (real leak filter; mock decomposer + Kimi)…")
    print("-" * 70)

    # Patch decompose_draft so it returns our canned list instead of calling Claude.
    with patch(
        "orchestrator.stages.stage3_verification.decompose_draft",
        AsyncMock(return_value=MOCK_QUESTIONS),
    ):
        result = await stage3_cove_verify(
            prompt=OPERATOR_PROMPT,
            draft_text=DRAFT,
            framing_note=FRAMING_NOTE,
            kimi=MockKimi(),
            transcript=None,
        )

    print(f"\nstage: {result['stage']}")
    print(f"non_voting: {result['non_voting']}")
    print(f"questions ({len(result['questions'])}):")
    for q in result["questions"]:
        print(f"  - {q}")
    print(f"\nanswers ({len(result['answers'])}):")
    for a in result["answers"]:
        print(f"  - {a['answer'][:120]}  (conf={a['confidence']:.2f})")
    print("\ncomparison:")
    print(f"  agreements:    {result['comparison']['agreements']}")
    print(f"  disagreements: {result['comparison']['disagreements']}")
    print(f"  comparator_mode: {result['comparison']['comparator_mode']}")
    print(f"  flagged: {len(result['comparison']['flagged'])}")
    print(f"\ntriggers_revision: {result['triggers_revision']}")

    print("\n" + "=" * 70)
    print("OK — the pipeline ran end-to-end with no real LLM calls.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
