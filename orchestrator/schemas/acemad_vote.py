"""AceMAD vote schema — discrete verdict + self-belief + peer-prediction (§7.5)."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Verdict = Literal["APPROVE", "REJECT", "MODIFY"]


class Vote(BaseModel):
    """One voter's contribution to Stage 4 AceMAD aggregation.

    peer_prediction is a discrete distribution over the (other_voter, verdict)
    outcome space. With 4 other voters × 3 verdicts the space size is 12.
    With Grok stubbed (4-voter council), the space is 3 other × 3 verdicts = 9.
    Keys are stringified tuples "(other_voter, verdict)"; values must sum to 1.0.
    """
    model_config = {"extra": "forbid"}

    voter: str
    verdict: Verdict
    self_belief: float = Field(ge=0.0, le=1.0)
    peer_prediction: dict[str, float]
    rationale: str
