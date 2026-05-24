"""Stage output schemas — shared between adapters, stages, and telemetry."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Verdict = Literal["APPROVE", "REJECT", "MODIFY"]


class MemberResult(BaseModel):
    """What a contributing adapter returns from `ask()`."""
    # protected_namespaces=() silences the harmless pydantic warning that
    # `model_used` collides with the protected `model_` prefix.
    model_config = {"extra": "forbid", "protected_namespaces": ()}

    member: str
    text: str                     # full response text
    verdict: Verdict | None = None  # parsed from text; None if absent
    model_used: str | None = None  # what the CLI reported (for model-pin assertion)
    duration_s: float = 0.0
    tokens_in: int | None = None
    tokens_out: int | None = None


class DroppedResult(BaseModel):
    """Adapter could not respond; spec §6 Stage 2 keeps going if ≥3 voters return."""
    model_config = {"extra": "forbid"}

    member: str
    reason: str                   # short machine token: "timeout" | "auth_error" | "model_mismatch" | ...
    detail: str | None = None
    auth_error: bool = False      # if True, supervisor aborts and prompts operator


class VerifierAnswer(BaseModel):
    """What the Verifier (Kimi) returns for one factored question."""
    model_config = {"extra": "forbid", "protected_namespaces": ()}

    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    model_used: str | None = None
