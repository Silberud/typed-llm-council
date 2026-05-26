"""ClaimJudgment — Phase E.2 real-comparator output schema.

The placeholder comparator returns aggregate counts derived from per-answer
confidence. The real comparator (Phase E.2) returns per-question structured
judgments produced by a Claude judge that has access to the draft, the
question, and the verifier's answer.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Judgment = Literal["SUPPORT", "CONTRADICT", "NOT_RELATE"]


class ClaimJudgment(BaseModel):
    """One question's comparator judgment."""
    model_config = {"extra": "forbid"}

    question_index: int = Field(ge=0)
    judgment: Judgment
    rationale: str = Field(min_length=1, max_length=600)
