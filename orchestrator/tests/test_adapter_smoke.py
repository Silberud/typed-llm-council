"""Phase B smoke tests — structural checks only, no live API calls.

Verifies the spec's Phase B acceptance criteria (§11):
  - All 6 adapters import and instantiate.
  - Adapters expose the correct method shape (Contributing has ask, Kimi does not).
  - Auth check returns False (not raises) when broken.
  - Grok adapter is a permanent stub (returns DroppedResult).
  - Kimi adapter rejects any input that isn't a VerifierInput (Pydantic ValidationError).
"""
import asyncio
import inspect
import pytest
from pydantic import ValidationError

from orchestrator.adapters.base import (
    MemberAdapter, ContributingAdapter, VerifierAdapter,
)
from orchestrator.adapters.claude import ClaudeAdapter
from orchestrator.adapters.gemini import GeminiAdapter
from orchestrator.adapters.gpt import GPTAdapter
from orchestrator.adapters.qwen import QwenAdapter
from orchestrator.adapters.grok import GrokAdapter
from orchestrator.adapters.kimi import KimiAdapter
from orchestrator.schemas.verifier_input import VerifierInput
from orchestrator.schemas.stage_output import DroppedResult


CONTRIBUTORS = [ClaudeAdapter, GeminiAdapter, GPTAdapter, QwenAdapter, GrokAdapter]


def test_all_six_adapters_instantiate():
    for cls in CONTRIBUTORS:
        a = cls()
        assert isinstance(a, MemberAdapter)
        assert isinstance(a, ContributingAdapter)
        assert a.name
    k = KimiAdapter()
    assert isinstance(k, MemberAdapter)
    assert isinstance(k, VerifierAdapter)
    assert k.name == "kimi"


def test_kimi_is_not_a_contributing_adapter():
    """Structural: Kimi must NOT be in the ContributingAdapter hierarchy."""
    assert not isinstance(KimiAdapter(), ContributingAdapter)


def test_kimi_has_no_ask_method():
    """Spec invariant #2/#7 + EX-001: KimiAdapter must not expose .ask()."""
    a = KimiAdapter()
    assert not hasattr(a, "ask") or not callable(getattr(a, "ask", None))
    assert hasattr(a, "ask_verifier") and callable(a.ask_verifier)


def test_kimi_ask_verifier_typed_with_VerifierInput():
    sig = inspect.signature(KimiAdapter.ask_verifier)
    params = list(sig.parameters.values())
    assert len(params) >= 2
    assert params[1].annotation == VerifierInput


def test_verifier_input_rejects_extra_fields():
    with pytest.raises(ValidationError):
        VerifierInput(operator_prompt="p", verification_question="q", draft_text="leak!")


def test_verifier_input_is_frozen():
    v = VerifierInput(operator_prompt="p", verification_question="q")
    with pytest.raises(ValidationError):
        v.operator_prompt = "mutated"


def test_grok_is_stubbed_and_always_drops():
    a = GrokAdapter()
    # auth_check returns False, never raises
    assert asyncio.run(a.auth_check()) is False
    result = asyncio.run(a.ask("any prompt"))
    assert isinstance(result, DroppedResult)
    assert result.member == "grok"
    assert "x_premium" in result.reason or "no_oauth" in result.reason


def test_auth_check_returns_bool_not_raises_when_broken():
    """Spec §11 Phase B: 'Auth-check returns False not exception when broken.'"""
    for cls in CONTRIBUTORS:
        a = cls()
        result = asyncio.run(a.auth_check())
        assert isinstance(result, bool), f"{cls.__name__}.auth_check() returned {type(result).__name__}"


def test_kimi_ask_verifier_rejects_non_VerifierInput_at_runtime():
    """Belt-and-suspenders runtime check (Hermes finding #9): even though the
    annotation says VerifierInput, a duck-typed object with the right
    attributes would otherwise sneak through. ask_verifier must raise
    TypeError on anything that isn't an actual VerifierInput instance."""
    class FakeInput:
        operator_prompt = "x"
        verification_question = "y"
    k = KimiAdapter()
    with pytest.raises(TypeError, match="VerifierInput"):
        asyncio.run(k.ask_verifier(FakeInput()))
    with pytest.raises(TypeError, match="VerifierInput"):
        asyncio.run(k.ask_verifier({"operator_prompt": "x", "verification_question": "y"}))


def test_kimi_endpoint_allowlist():
    """Hermes finding #12: arbitrary endpoint URL would exfiltrate Bearer token."""
    from orchestrator.adapters.kimi import _validate_endpoint
    # Allowed
    _validate_endpoint("https://api.moonshot.ai/v1/chat/completions")
    _validate_endpoint("https://api.moonshot.cn/v1/chat/completions")
    # HTTP rejected
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_endpoint("http://api.moonshot.ai/v1/chat/completions")
    # Non-allowlisted host rejected
    with pytest.raises(ValueError, match="allowlist"):
        _validate_endpoint("https://api.attacker.com/v1/chat/completions")
