"""VerifierInput — the ONLY input shape the Kimi (K2.6) adapter accepts.

Enforces spec invariants #2 and #7:
  - Verifier is non-voting and receives no draft, framing, or council content.
  - Pydantic frozen + extra='forbid' makes any leakage attempt a ValidationError.

CI: tests/test_cove_isolation.py exercises this contract at every commit.
"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field


class VerifierInput(BaseModel):
    """Locked-down payload for the Verifier seat.

    Forbidden by design: any field referring to Draft D, framing note, advocate
    defence, juror critiques, persona prompts, or any other council stage output.
    Unknown fields raise ValidationError; mutation raises ValidationError.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator_prompt: str = Field(min_length=1, max_length=10_000)
    verification_question: str = Field(min_length=1, max_length=2_000)
