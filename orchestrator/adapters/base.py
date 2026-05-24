"""Adapter base classes.

Two distinct adapter shapes — structurally separated so the Verifier seat
CANNOT accept generic prompts (enforcing spec invariants #2 and #7):

  MemberAdapter           — common base; has name + auth_check
    ├─ ContributingAdapter  — adds ask(prompt) → MemberResult|DroppedResult
    │                          (Claude, Gemini, GPT, Qwen, Grok)
    └─ VerifierAdapter      — adds ask_verifier(VerifierInput) → VerifierAnswer
                               (Kimi only)

Because KimiAdapter inherits from VerifierAdapter (NOT ContributingAdapter),
it has no `ask()` method at all. CI test (test_cove_isolation.py) verifies
this structurally with hasattr/inspect.signature.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from orchestrator.schemas.stage_output import MemberResult, DroppedResult, VerifierAnswer
from orchestrator.schemas.verifier_input import VerifierInput


class MemberAdapter(ABC):
    """Shared base — every seat (voting or verifying) has a name and an auth check."""

    name: str = "<unset>"

    @abstractmethod
    async def auth_check(self) -> bool:
        """Return True if the underlying CLI / API credential is currently valid.
        MUST NOT raise on broken auth — return False instead (spec §11 Phase B)."""
        ...


class ContributingAdapter(MemberAdapter):
    """Voting adapter — five seats (Claude, Gemini, GPT, Qwen, Grok)."""

    @abstractmethod
    async def ask(self, prompt: str, *, timeout: float = 90.0) -> MemberResult | DroppedResult:
        """Send an open-ended prompt to the underlying model; return parsed result.
        Must complete within `timeout` seconds; otherwise return DroppedResult."""
        ...


class VerifierAdapter(MemberAdapter):
    """Non-voting verifier adapter — Kimi only. NO ask() method by design."""

    @abstractmethod
    async def ask_verifier(self, input: VerifierInput) -> VerifierAnswer:
        """The ONLY method the verifier exposes. Input is typed at the schema
        level (frozen + extra=forbid) — there is no field shape that would let
        draft/framing/persona content cross the boundary."""
        ...
