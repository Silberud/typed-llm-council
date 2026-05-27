"""Convergence Council Protocol ledger schemas.

The ledger is deliberately deterministic and provider-agnostic.  It records the
strict loop the project wants to productise:

    draft/revise artifact -> review -> judge -> repeat until 3 clean rounds

The key invariant is that *material required changes* reset convergence while
optional suggestions do not.  This keeps council loops strong, simple, and
terminating instead of turning every nice-to-have into an infinite blocker.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Phase(str, Enum):
    """The two convergence phases supported by the protocol."""

    PLAN = "PLAN"
    EXECUTION = "EXECUTION"


class ReviewVerdict(str, Enum):
    """Finite reviewer verdict set used across providers."""

    APPROVE = "APPROVE"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


class Severity(str, Enum):
    """Materiality level for reviewer-requested changes."""

    BLOCKER = "BLOCKER"
    MATERIAL = "MATERIAL"


class RunStatus(str, Enum):
    """Lifecycle state for a convergence run."""

    RUNNING = "RUNNING"
    CONVERGED = "CONVERGED"
    BLOCKED = "BLOCKED"
    FAILED_MAX_ROUNDS = "FAILED_MAX_ROUNDS"


class ReviewRequiredChange(BaseModel):
    """A material change requested by one reviewer."""

    model_config = {"extra": "forbid"}

    id: str
    description: str
    severity: Severity = Severity.MATERIAL
    evidence_or_reason: str


class OptionalSuggestion(BaseModel):
    """A non-blocking improvement candidate.

    Optional suggestions are preserved for future work but never reset the clean
    round counter unless the Judge explicitly promotes them into a material
    required change in ``JudgeDecision.material_required_changes``.
    """

    model_config = {"extra": "forbid"}

    description: str
    rationale: str | None = None


class CouncilReview(BaseModel):
    """One provider/role review of the current artifact version."""

    model_config = {"extra": "forbid"}

    reviewer_id: str
    provider: str
    role: str
    verdict: ReviewVerdict
    required_changes: list[ReviewRequiredChange] = Field(default_factory=list)
    optional_suggestions: list[OptionalSuggestion] = Field(default_factory=list)
    main_risk: str
    evidence_checked: list[str] = Field(default_factory=list)
    blind_spots_or_assumptions: list[str] = Field(default_factory=list)
    confidence: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def verdict_matches_required_changes(self) -> "CouncilReview":
        """APPROVE means no material changes are being requested."""
        if self.verdict == ReviewVerdict.APPROVE and self.required_changes:
            msg = "APPROVE reviews cannot include required_changes"
            raise ValueError(msg)
        if self.verdict in {ReviewVerdict.MODIFY, ReviewVerdict.REJECT} and not self.required_changes:
            msg = "MODIFY/REJECT reviews must include at least one required change"
            raise ValueError(msg)
        return self


class RejectedRequiredChange(BaseModel):
    """A reviewer-requested change the Judge rejected as non-material."""

    model_config = {"extra": "forbid"}

    id: str
    source_reviewer: str
    reason_rejected_as_non_material: str


class MaterialRequiredChange(BaseModel):
    """A material change accepted by the Judge and required before convergence."""

    model_config = {"extra": "forbid"}

    id: str
    source_reviewers: list[str]
    description: str
    acceptance_criteria: str
    severity: Severity = Severity.MATERIAL


class RemainingDissent(BaseModel):
    """Dissent preserved in the ledger after the Judge decision."""

    model_config = {"extra": "forbid"}

    reviewer_id: str
    summary: str
    material: bool


class JudgeDecision(BaseModel):
    """Chair/Judge synthesis for one convergence round."""

    model_config = {"extra": "forbid"}

    verdict: ReviewVerdict
    material_required_changes: list[MaterialRequiredChange] = Field(default_factory=list)
    rejected_required_changes: list[RejectedRequiredChange] = Field(default_factory=list)
    optional_suggestions: list[OptionalSuggestion] = Field(default_factory=list)
    dissent_remaining: list[RemainingDissent] = Field(default_factory=list)
    evidence_gates_passed: bool
    clean_round: bool
    confidence: int = Field(ge=0, le=100)
    rationale: str

    @model_validator(mode="after")
    def clean_round_is_strict(self) -> "JudgeDecision":
        """Clean rounds require no material changes, no material dissent, and evidence."""
        has_material_dissent = any(d.material for d in self.dissent_remaining)
        if self.clean_round:
            problems = []
            if self.verdict != ReviewVerdict.APPROVE:
                problems.append("verdict must be APPROVE")
            if self.material_required_changes:
                problems.append("material_required_changes must be empty")
            if has_material_dissent:
                problems.append("material dissent must be resolved")
            if not self.evidence_gates_passed:
                problems.append("evidence_gates_passed must be true")
            if problems:
                raise ValueError("clean_round invalid: " + "; ".join(problems))
        return self

    def confidence_cap(self) -> int:
        """Return the maximum defensible confidence for this decision.

        The caps intentionally encode humility: missing evidence, unresolved
        material dissent, and requested modifications all limit confidence even
        if prose sounds persuasive.
        """
        cap = 100
        if not self.evidence_gates_passed:
            cap = min(cap, 60)
        if any(d.material for d in self.dissent_remaining):
            cap = min(cap, 75)
        if self.material_required_changes:
            cap = min(cap, 80)
        if self.verdict == ReviewVerdict.REJECT:
            cap = min(cap, 70)
        return cap

    @model_validator(mode="after")
    def confidence_respects_caps(self) -> "JudgeDecision":
        cap = self.confidence_cap()
        if self.confidence > cap:
            msg = f"confidence {self.confidence} exceeds cap {cap} for this decision"
            raise ValueError(msg)
        return self


class ConvergenceRound(BaseModel):
    """One review/Judge cycle over a specific artifact version."""

    model_config = {"extra": "forbid"}

    round_number: int = Field(ge=1)
    artifact_version: int = Field(ge=1)
    reviews: list[CouncilReview]
    judge: JudgeDecision


class ConvergenceLedger(BaseModel):
    """Append-only ledger for plan or execution convergence."""

    model_config = {"extra": "forbid"}

    run_id: str
    goal: str
    phase: Phase
    artifact_id: str
    clean_rounds_required: int = Field(default=3, ge=1)
    max_rounds: int = Field(default=9, ge=1)
    rounds: list[ConvergenceRound] = Field(default_factory=list)
    status: RunStatus = RunStatus.RUNNING

    @property
    def consecutive_clean_rounds(self) -> int:
        """Count clean rounds from the end of the ledger backwards."""
        count = 0
        for round_ in reversed(self.rounds):
            if not round_.judge.clean_round:
                break
            count += 1
        return count

    @property
    def converged(self) -> bool:
        """True when the configured clean-round threshold is reached."""
        return self.consecutive_clean_rounds >= self.clean_rounds_required

    def with_round(self, round_: ConvergenceRound) -> "ConvergenceLedger":
        """Return a new ledger with ``round_`` appended and status updated."""
        next_rounds = [*self.rounds, round_]
        next_ledger = self.model_copy(update={"rounds": next_rounds})
        if next_ledger.converged:
            return next_ledger.model_copy(update={"status": RunStatus.CONVERGED})
        if len(next_rounds) >= self.max_rounds:
            return next_ledger.model_copy(update={"status": RunStatus.FAILED_MAX_ROUNDS})
        return next_ledger.model_copy(update={"status": RunStatus.RUNNING})
