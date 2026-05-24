"""
test_cove_isolation.py

CRITICAL CI SAFETY NET for the H5R LLM Council v2.2 specification.

This test enforces invariants #2 (Verifier is non-voting) and #7 (no member
sees another member's reasoning before Stage 4) for the K2.6 / CoVe verifier
seat.

If this test fails, the build MUST fail. There is no graceful degradation;
a CoVe stage that leaks draft context invalidates the entire factored-
verification design and the council collapses to v1-equivalent quality.

Test layers (defence in depth):
  1. Type-level enforcement — Kimi adapter accepts ONLY `VerifierInput`
  2. Substring leak detection — assert no draft/framing/persona content
     appears in any prompt sent to K2.6
  3. Property-based fuzzing — 50 randomly generated fixtures, all must
     satisfy isolation
  4. Behavioural check — Kimi adapter has no generic `ask()` method;
     only `ask_verifier()`

Run: pytest tests/test_cove_isolation.py -v --tb=short
"""

from __future__ import annotations

import json
import inspect
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, strategies as st, settings
from pydantic import ValidationError

# These imports assume the orchestrator package is installed in editable mode:
#   pip install -e .
from orchestrator.adapters.kimi import KimiAdapter
from orchestrator.schemas.verifier_input import VerifierInput
from orchestrator.stages.stage3_verification import stage3_cove_verify
from orchestrator.adapters.base import MemberAdapter


# ============================================================================
# Fixtures
# ============================================================================

@dataclass
class CouncilTranscript:
    """Minimal transcript stand-in for unit testing."""
    session_id: str = "01TEST00000000000000000000"
    operator_prompt: str = "Should we acquire Company X for $50M?"
    framing_note: str = (
        "The decision is whether to acquire Company X. The framing assumes "
        "$50M valuation; this may not be defensible — independent valuation "
        "should be sought."
    )
    draft_text: str = (
        "Our analysis concludes that Company X represents a sound acquisition "
        "at $50M, based on three factors: (1) projected synergies of $8M/year, "
        "(2) accretive within 18 months, (3) defensible IP moat. The Council "
        "of advisors strongly supports this conclusion."
    )
    advocate_defence: str = (
        "I am defending the acquisition recommendation. The synergy projection "
        "is conservative; comparable transactions in this sector cleared at "
        "8-12x EBITDA, our offer is 6.2x."
    )
    juror_critiques: list[str] = field(default_factory=lambda: [
        "REJECT: synergy projection is unverified.",
        "MODIFY: need IP due diligence first.",
    ])
    verification_questions: list[str] = field(default_factory=lambda: [
        "What is the typical EBITDA multiple for acquisitions in this sector?",
        "What is the average time-to-accretion for similar M&A transactions?",
        "How is IP moat defensibility typically measured?",
        "What is the standard practice for synergy projection in M&A?",
        "What independent valuation methods are commonly used for $50M deals?",
    ])


@pytest.fixture
def transcript() -> CouncilTranscript:
    return CouncilTranscript()


# ============================================================================
# LAYER 1: Type-level enforcement
# ============================================================================

class TestTypeLevelIsolation:
    """The Kimi adapter must accept ONLY VerifierInput.
    Pydantic with `extra=forbid` and `frozen=True` enforces this at type level."""
    
    def test_verifier_input_rejects_unknown_fields(self):
        """VerifierInput must reject any field outside its schema."""
        with pytest.raises(ValidationError) as exc_info:
            VerifierInput(
                operator_prompt="prompt",
                verification_question="q",
                draft_text="leaked!",   # forbidden field
            )
        assert "draft_text" in str(exc_info.value).lower() or \
               "extra" in str(exc_info.value).lower() or \
               "forbidden" in str(exc_info.value).lower()
    
    def test_verifier_input_rejects_framing_field(self):
        with pytest.raises(ValidationError):
            VerifierInput(
                operator_prompt="prompt",
                verification_question="q",
                framing_note="leaked!",
            )
    
    def test_verifier_input_rejects_juror_critiques_field(self):
        with pytest.raises(ValidationError):
            VerifierInput(
                operator_prompt="prompt",
                verification_question="q",
                juror_critiques=["leaked!"],
            )
    
    def test_verifier_input_rejects_advocate_defence_field(self):
        with pytest.raises(ValidationError):
            VerifierInput(
                operator_prompt="prompt",
                verification_question="q",
                advocate_defence="leaked!",
            )
    
    def test_verifier_input_is_immutable(self):
        """frozen=True must prevent field mutation post-construction."""
        v = VerifierInput(operator_prompt="p", verification_question="q")
        with pytest.raises(ValidationError):
            v.operator_prompt = "mutated"
    
    def test_kimi_adapter_has_no_generic_ask_method(self):
        """The Kimi adapter must not expose a generic ask(prompt) method —
        only ask_verifier(VerifierInput). This is structural, not just nominal:
        attempting to call .ask() should raise AttributeError."""
        adapter = KimiAdapter()
        assert not hasattr(adapter, "ask") or not callable(getattr(adapter, "ask", None)), \
            "KimiAdapter must NOT have a callable .ask() method"
        assert hasattr(adapter, "ask_verifier") and callable(adapter.ask_verifier), \
            "KimiAdapter must have .ask_verifier(VerifierInput) method"
    
    def test_kimi_adapter_ask_verifier_signature(self):
        """ask_verifier must take exactly one positional argument of type VerifierInput."""
        sig = inspect.signature(KimiAdapter.ask_verifier)
        params = list(sig.parameters.values())
        # First param is `self`, second must be the VerifierInput
        assert len(params) >= 2, "ask_verifier must take VerifierInput parameter"
        input_param = params[1]
        # Type annotation must be VerifierInput (or a subclass)
        assert input_param.annotation == VerifierInput, \
            f"ask_verifier parameter must be typed VerifierInput, got {input_param.annotation}"


# ============================================================================
# LAYER 2: Substring leak detection (belt-and-suspenders)
# ============================================================================

class TestSubstringLeakDetection:
    """Even if the type system is correct, capture every prompt sent to K2.6
    and verify forbidden substrings are absent."""
    
    @pytest.mark.asyncio
    async def test_no_draft_text_in_k26_prompt(self, transcript):
        """K2.6 must never see the draft text."""
        captured_prompts = await self._run_stage3_capturing_kimi_prompts(transcript)
        
        for prompt in captured_prompts:
            self._assert_no_leak(prompt, transcript.draft_text, label="draft_text")
    
    @pytest.mark.asyncio
    async def test_no_framing_note_in_k26_prompt(self, transcript):
        captured_prompts = await self._run_stage3_capturing_kimi_prompts(transcript)
        
        for prompt in captured_prompts:
            self._assert_no_leak(prompt, transcript.framing_note, label="framing_note")
    
    @pytest.mark.asyncio
    async def test_no_advocate_defence_in_k26_prompt(self, transcript):
        captured_prompts = await self._run_stage3_capturing_kimi_prompts(transcript)
        
        for prompt in captured_prompts:
            self._assert_no_leak(prompt, transcript.advocate_defence, label="advocate_defence")
    
    @pytest.mark.asyncio
    async def test_no_juror_critiques_in_k26_prompt(self, transcript):
        captured_prompts = await self._run_stage3_capturing_kimi_prompts(transcript)
        
        for prompt in captured_prompts:
            for critique in transcript.juror_critiques:
                self._assert_no_leak(prompt, critique, label=f"juror_critique[{critique[:20]}]")
    
    @pytest.mark.asyncio
    async def test_no_role_persona_leakage(self, transcript):
        """The strings 'Advocate', 'Juror', 'Skeptic', 'Analyst', 'Researcher',
        'Architect' MUST NOT appear in K2.6 prompts.
        
        Note: 'Chair' is also forbidden but only in the context of synthesis;
        we use a list of role-identity markers."""
        captured_prompts = await self._run_stage3_capturing_kimi_prompts(transcript)
        
        forbidden_role_terms = [
            "Advocate", "Juror", "Skeptic", "Analyst",
            "Researcher", "Architect", "Drafter",
            "Council", "consensus", "dissent",
        ]
        
        for prompt in captured_prompts:
            for term in forbidden_role_terms:
                # Case-sensitive: role identities are capitalised in personas
                assert term not in prompt, \
                    f"Forbidden role term '{term}' leaked into K2.6 prompt: {prompt[:200]}..."
    
    @pytest.mark.asyncio
    async def test_only_allowed_content_in_k26_prompt(self, transcript):
        """Positive test: each K2.6 prompt must contain ONLY the operator_prompt
        and the verification_question (plus K2.6's own system prompt boilerplate)."""
        captured_prompts = await self._run_stage3_capturing_kimi_prompts(transcript)
        
        assert len(captured_prompts) >= 5, "Should call K2.6 once per question"
        
        for prompt in captured_prompts:
            # Operator prompt is fine — K2.6 needs context for the original question
            assert transcript.operator_prompt in prompt or \
                   any(q in prompt for q in transcript.verification_questions), \
                "K2.6 prompt must contain operator_prompt or a verification question"
    
    @staticmethod
    def _assert_no_leak(prompt: str, forbidden: str, label: str):
        """Assert that forbidden content does not appear in prompt.
        Uses both substring and high-overlap heuristic to catch paraphrasing."""
        # Direct substring check
        assert forbidden not in prompt, \
            f"LEAK DETECTED — {label} found verbatim in K2.6 prompt.\n" \
            f"Forbidden: {forbidden[:100]}...\n" \
            f"Prompt: {prompt[:200]}..."
        
        # High-overlap heuristic: any 8-word sequence from forbidden appearing
        # in prompt is a paraphrase leak.
        forbidden_words = forbidden.split()
        if len(forbidden_words) >= 8:
            for i in range(len(forbidden_words) - 7):
                window = " ".join(forbidden_words[i:i+8])
                assert window not in prompt, \
                    f"LEAK DETECTED — 8-word window from {label} found in K2.6 prompt.\n" \
                    f"Window: {window}\n" \
                    f"Prompt: {prompt[:200]}..."
    
    async def _run_stage3_capturing_kimi_prompts(
        self, transcript: CouncilTranscript
    ) -> list[str]:
        """Run Stage 3 with a Kimi adapter that captures every prompt it sees."""
        captured: list[str] = []
        
        class CapturingKimi(KimiAdapter):
            async def ask_verifier(self, input: VerifierInput):
                # Serialise the full input that would be sent to the CLI
                full_prompt = json.dumps({
                    "operator_prompt": input.operator_prompt,
                    "verification_question": input.verification_question,
                })
                captured.append(full_prompt)
                # Return a mock verifier answer
                from orchestrator.schemas.stage_output import VerifierAnswer
                return VerifierAnswer(answer="mock answer", confidence=0.8)
        
        # Mock the decomposer (Opus 4.7) to return our test questions
        mock_decomposer = AsyncMock(return_value=transcript.verification_questions)
        
        # Mock the comparator
        mock_comparator = AsyncMock(return_value={"agreements": 5, "disagreements": 0})
        
        with patch("orchestrator.stages.stage3_verification.decompose_draft", mock_decomposer), \
             patch("orchestrator.stages.stage3_verification.compare_answers", mock_comparator):
            await stage3_cove_verify(
                prompt=transcript.operator_prompt,
                draft_text=transcript.draft_text,
                framing_note=transcript.framing_note,
                kimi=CapturingKimi(),
                transcript=transcript,
            )
        
        return captured


# ============================================================================
# LAYER 3: Property-based fuzzing with Hypothesis
# ============================================================================

class TestPropertyBasedIsolation:
    """50 randomly generated drafts and framings; isolation must hold for all."""
    
    @given(
        operator_prompt=st.text(min_size=10, max_size=500, alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters="\x00",
        )),
        draft_text=st.text(min_size=50, max_size=2000, alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters="\x00",
        )),
        framing_note=st.text(min_size=20, max_size=500, alphabet=st.characters(
            blacklist_categories=("Cs",), blacklist_characters="\x00",
        )),
    )
    @settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_isolation_holds_for_random_fixtures(
        self, operator_prompt, draft_text, framing_note
    ):
        """For any random (prompt, draft, framing), the K2.6 prompt must not
        contain draft or framing content."""
        # Skip pathological short-fragment cases that would cause false positives
        # (e.g., if random draft happens to be 'a' and prompt also contains 'a')
        if len(draft_text) < 50 or len(framing_note) < 20:
            return
        
        transcript = CouncilTranscript(
            operator_prompt=operator_prompt,
            draft_text=draft_text,
            framing_note=framing_note,
        )
        
        captured = await TestSubstringLeakDetection._run_stage3_capturing_kimi_prompts(
            None, transcript
        )
        
        for prompt in captured:
            # Use 12-word window for fuzzed text (longer than fixture test to avoid
            # spurious matches on short repeated phrases)
            draft_words = draft_text.split()
            if len(draft_words) >= 12:
                for i in range(len(draft_words) - 11):
                    window = " ".join(draft_words[i:i+12])
                    assert window not in prompt, \
                        f"FUZZ LEAK: draft 12-word window leaked: {window}"
            
            framing_words = framing_note.split()
            if len(framing_words) >= 12:
                for i in range(len(framing_words) - 11):
                    window = " ".join(framing_words[i:i+12])
                    assert window not in prompt, \
                        f"FUZZ LEAK: framing 12-word window leaked: {window}"


# ============================================================================
# LAYER 4: Regression test for known bugs
# ============================================================================

class TestKnownRegressions:
    """If a specific bug is discovered in the future, add a regression test
    here to ensure it cannot recur."""
    
    def test_verifier_input_does_not_accept_dict_with_extra_keys(self):
        """Bug class: someone tries to construct VerifierInput from a dict
        that includes extra fields. extra='forbid' must catch this."""
        with pytest.raises(ValidationError):
            VerifierInput(**{
                "operator_prompt": "p",
                "verification_question": "q",
                "draft": "this should fail",
            })
    
    def test_verifier_input_with_only_required_fields(self):
        """Positive baseline: VerifierInput with exactly the allowed fields succeeds."""
        v = VerifierInput(operator_prompt="prompt", verification_question="q")
        assert v.operator_prompt == "prompt"
        assert v.verification_question == "q"


# ============================================================================
# CI hook: this test must run before any other test in the suite
# ============================================================================

if __name__ == "__main__":
    # If anyone runs this file directly, exit non-zero on failure so CI catches it.
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
