"""Tests for the Stage 3 leak filter (Tier 1 hardening, 2026-05-25).

Validates:
  - Clean questions pass (the CoVe-normal case)
  - Verbatim draft windows are blocked
  - Framing windows are blocked
  - Role/council-meta markers are blocked
  - Markers present in the operator prompt are allowed through
  - Stage 3 fails closed when a leaky decomposer produces a leaky question

This is the regression test Hermes's review identified as missing: the
existing test_cove_isolation.py mocks `decompose_draft` to return clean
questions, so it can't prove what happens when the decomposer leaks.
"""
import pytest
from unittest.mock import AsyncMock, patch

from orchestrator.services.leak_filter import (
    LeakDetectedError, check_leak, check_inputs_clean,
)
from orchestrator.stages.stage3_verification import stage3_cove_verify
from orchestrator.adapters.kimi import KimiAdapter


# ---------- unit tests for the filter itself ----------

def test_clean_cove_question_passes():
    """The CoVe-normal case: short claim restatement in a question."""
    check_leak(
        question="Does Python 3.12 include PEP 695?",
        operator_prompt="Summarise Python 3.12 features.",
        draft_text="Python 3.12 was released on 3 October 2023. It includes PEP 695, PEP 698, and PEP 701.",
        framing_note="Reader is an engineering team.",
    )  # no exception expected


def test_long_verbatim_window_blocked():
    """8-word window from draft appearing in question is a leak."""
    with pytest.raises(LeakDetectedError) as exc:
        check_leak(
            question="Confirm: Python 3.12 was released on 3 October 2023 and includes PEP 695.",
            operator_prompt="Summarise Python 3.12.",
            draft_text="Python 3.12 was released on 3 October 2023 and includes PEP 695.",
            framing_note="",
        )
    assert "window from draft" in str(exc.value)


def test_framing_window_blocked():
    with pytest.raises(LeakDetectedError) as exc:
        check_leak(
            question="Is the reader an engineering team deciding whether to migrate this quarter?",
            operator_prompt="Summarise Python 3.12.",
            draft_text="",
            framing_note="The reader is an engineering team deciding whether to migrate this quarter.",
        )
    assert "framing" in str(exc.value)


@pytest.mark.parametrize("phrase", [
    "the advocate", "the juror", "the skeptic", "the council",
    "council concluded", "draft says", "the draft", "peer review",
])
def test_role_marker_phrase_blocked(phrase):
    """Multi-word role markers signal council-meta injection."""
    with pytest.raises(LeakDetectedError) as exc:
        check_leak(
            question=f"What did {phrase} say about Company X?"
                     if not phrase.startswith("draft") and not phrase.startswith("council")
                     else f"In this response, {phrase} that Company X is sound.",
            operator_prompt="Should we acquire Company X?",
            draft_text="",
            framing_note="",
        )
    assert phrase in str(exc.value).lower()


def test_single_word_council_in_operator_prompt_no_longer_false_positive():
    """Regression: Hypothesis found operator_prompt='COUNCIL000' triggering
    leak detection on bare 'council'. Multi-word-only markers fix this so
    legitimate operator vocabulary using 'council', 'consensus', etc. as
    single words doesn't false-positive."""
    # This used to raise — now must NOT raise.
    check_leak(
        question="What is a council?",
        operator_prompt="COUNCIL000",
        draft_text="00000000000000000000000000000000000000000000000000",
        framing_note="00000000000000000000",
    )
    check_inputs_clean(
        operator_prompt="COUNCIL000",
        verification_question="What is a council?",
        draft_text="00000000000000000000000000000000000000000000000000",
        framing_note="00000000000000000000",
    )


def test_marker_in_operator_prompt_is_allowed():
    """If the operator legitimately uses a role-marker phrase, the question
    can use that phrase too (suppression based on operator's own prompt)."""
    check_leak(
        question="What did the advocate of free trade argue?",
        operator_prompt="Summarise what the advocate of free trade has historically argued.",
        draft_text="",
        framing_note="",
    )


def test_check_inputs_clean_blocks_tampered_operator_prompt():
    """Defensive: operator_prompt itself must be clean of draft content.
    Multi-word marker 'draft says' AND/OR the n-gram window match must catch this."""
    with pytest.raises(LeakDetectedError):
        check_inputs_clean(
            operator_prompt="The draft says: Company X is a sound acquisition at $50M",
            verification_question="Reply ok.",
            draft_text="Company X is a sound acquisition at $50M",
            framing_note="",
        )


# ---------- Stage 3 integration: fail closed on leaky decomposer ----------

class _Transcript:
    session_id = "leak-test"


@pytest.mark.asyncio
async def test_stage3_aborts_when_decomposer_returns_leaky_question():
    """The original failure mode Hermes called out:
    a malicious/buggy decomposer puts draft text into a question.
    Stage 3 must abort BEFORE Kimi receives it."""
    leaky_questions = [
        "Is the council's draft text accurate?",  # role-marker leak
        "Q2", "Q3", "Q4", "Q5",
    ]
    kimi_call_count = 0

    class CountingKimi(KimiAdapter):
        async def ask_verifier(self, input):  # type: ignore[override]
            nonlocal kimi_call_count
            kimi_call_count += 1
            from orchestrator.schemas.stage_output import VerifierAnswer
            return VerifierAnswer(answer="ok", confidence=0.9)

    with patch("orchestrator.stages.stage3_verification.decompose_draft",
               AsyncMock(return_value=leaky_questions)):
        with pytest.raises(RuntimeError) as exc:
            await stage3_cove_verify(
                prompt="Should we acquire Company X for $50M?",
                draft_text="Company X is a sound acquisition at $50M.",
                framing_note="",
                kimi=CountingKimi(),
                transcript=_Transcript(),
            )
        assert "leaky question" in str(exc.value)
    assert kimi_call_count == 0, "Kimi must NOT be called when leak is detected"


@pytest.mark.asyncio
async def test_stage3_passes_clean_questions_through():
    """Sanity: clean decomposer output reaches Kimi normally."""
    clean_questions = [
        "What is PEP 695?",
        "When was Python 3.12 released?",
        "What does PEP 698 introduce?",
        "What is the @override decorator?",
        "What does PEP 701 standardise?",
    ]
    kimi_calls = []

    class CapturingKimi(KimiAdapter):
        async def ask_verifier(self, input):  # type: ignore[override]
            kimi_calls.append((input.operator_prompt, input.verification_question))
            from orchestrator.schemas.stage_output import VerifierAnswer
            return VerifierAnswer(answer="ok", confidence=0.9)

    with patch("orchestrator.stages.stage3_verification.decompose_draft",
               AsyncMock(return_value=clean_questions)):
        result = await stage3_cove_verify(
            prompt="Summarise Python 3.12.",
            draft_text="Python 3.12 includes PEP 695, PEP 698, and PEP 701.",
            framing_note="Engineering team audience.",
            kimi=CapturingKimi(),
            transcript=_Transcript(),
        )
    assert len(kimi_calls) == len(clean_questions)
    assert len(result["answers"]) == len(clean_questions)
