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

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class StrictLedgerModel(BaseModel):
    """Base model for validated, immutable convergence ledger records."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class ReviewRequiredChange(StrictLedgerModel):
    """A material change requested by one reviewer."""

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: Severity = Severity.MATERIAL
    evidence_or_reason: str = Field(min_length=1)


class OptionalSuggestion(StrictLedgerModel):
    """A non-blocking improvement candidate.

    Optional suggestions are preserved for future work but never reset the clean
    round counter unless the Judge explicitly promotes them into a material
    required change in ``JudgeDecision.material_required_changes``.
    """

    description: str = Field(min_length=1)
    rationale: str | None = Field(default=None, min_length=1)


class CouncilReview(StrictLedgerModel):
    """One provider/role review of the current artifact version."""


    reviewer_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    role: str = Field(min_length=1)
    verdict: ReviewVerdict
    required_changes: tuple[ReviewRequiredChange, ...] = Field(default_factory=tuple)
    optional_suggestions: tuple[OptionalSuggestion, ...] = Field(default_factory=tuple)
    main_risk: str = Field(min_length=1)
    evidence_checked: tuple[str, ...] = Field(default_factory=tuple)
    blind_spots_or_assumptions: tuple[str, ...] = Field(default_factory=tuple)
    confidence: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def verdict_matches_required_changes(self) -> "CouncilReview":
        """APPROVE means no material changes are being requested."""
        if self.reviewer_id == "judge":
            msg = "reviewer_id 'judge' is reserved for Judge-originated material changes"
            raise ValueError(msg)
        if self.verdict == ReviewVerdict.APPROVE and self.required_changes:
            msg = "APPROVE reviews cannot include required_changes"
            raise ValueError(msg)
        if self.verdict in {ReviewVerdict.MODIFY, ReviewVerdict.REJECT} and not self.required_changes:
            msg = "MODIFY/REJECT reviews must include at least one required change"
            raise ValueError(msg)
        return self


class RejectedRequiredChange(StrictLedgerModel):
    """A reviewer-requested change the Judge rejected as non-material."""


    id: str = Field(min_length=1)
    source_reviewer: str = Field(min_length=1)
    reason_rejected_as_non_material: str = Field(min_length=1)


class MaterialRequiredChange(StrictLedgerModel):
    """A material change accepted by the Judge and required before convergence."""


    id: str = Field(min_length=1)
    source_reviewers: tuple[str, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    acceptance_criteria: str = Field(min_length=1)
    severity: Severity = Severity.MATERIAL


class RemainingDissent(StrictLedgerModel):
    """Dissent preserved in the ledger after the Judge decision."""


    reviewer_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    material: bool


class JudgeDecision(StrictLedgerModel):
    """Chair/Judge synthesis for one convergence round."""


    verdict: ReviewVerdict
    material_required_changes: tuple[MaterialRequiredChange, ...] = Field(default_factory=tuple)
    rejected_required_changes: tuple[RejectedRequiredChange, ...] = Field(default_factory=tuple)
    optional_suggestions: tuple[OptionalSuggestion, ...] = Field(default_factory=tuple)
    dissent_remaining: tuple[RemainingDissent, ...] = Field(default_factory=tuple)
    evidence_gates_passed: bool
    clean_round: bool
    confidence: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def clean_round_is_strict(self) -> "JudgeDecision":
        """Clean rounds and verdicts must agree with material findings."""
        has_material_dissent = any(d.material for d in self.dissent_remaining)
        if self.verdict == ReviewVerdict.APPROVE and self.material_required_changes:
            msg = "APPROVE judge decisions cannot include material_required_changes"
            raise ValueError(msg)
        if self.verdict in {ReviewVerdict.MODIFY, ReviewVerdict.REJECT} and not (
            self.material_required_changes or has_material_dissent
        ):
            msg = "MODIFY/REJECT judge decisions require material changes or material dissent"
            raise ValueError(msg)
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


class ConvergenceRound(StrictLedgerModel):
    """One review/Judge cycle over a specific artifact version."""


    round_number: int = Field(ge=1)
    artifact_version: int = Field(ge=1)
    reviews: tuple[CouncilReview, ...] = Field(min_length=1)
    judge: JudgeDecision

    @model_validator(mode="after")
    def reviewer_required_changes_are_accounted_for(self) -> "ConvergenceRound":
        """Every reviewer-requested material change must be accepted or rejected."""
        if self.judge.clean_round:
            reviews_without_evidence = sorted(
                review.reviewer_id for review in self.reviews if not review.evidence_checked
            )
            if reviews_without_evidence:
                msg = "clean rounds require each review to record evidence_checked: " + ", ".join(
                    reviews_without_evidence
                )
                raise ValueError(msg)

        proposed_by_id: dict[str, set[str]] = {}
        reviewer_ids = [review.reviewer_id for review in self.reviews]
        duplicate_reviewer_ids = sorted({reviewer_id for reviewer_id in reviewer_ids if reviewer_ids.count(reviewer_id) > 1})
        if duplicate_reviewer_ids:
            msg = "duplicate reviewer_id values: " + ", ".join(duplicate_reviewer_ids)
            raise ValueError(msg)
        reviewer_id_set = set(reviewer_ids)

        dissent_reviewer_ids = [dissent.reviewer_id for dissent in self.judge.dissent_remaining]
        duplicate_dissent_reviewer_ids = sorted(
            {reviewer_id for reviewer_id in dissent_reviewer_ids if dissent_reviewer_ids.count(reviewer_id) > 1}
        )
        if duplicate_dissent_reviewer_ids:
            msg = "duplicate dissent_remaining reviewer_id values: " + ", ".join(duplicate_dissent_reviewer_ids)
            raise ValueError(msg)
        unknown_dissent_reviewer_ids = sorted(set(dissent_reviewer_ids) - reviewer_id_set)
        if unknown_dissent_reviewer_ids:
            msg = "dissent_remaining reviewer_id values unknown: " + ", ".join(unknown_dissent_reviewer_ids)
            raise ValueError(msg)

        for review in self.reviews:
            change_ids = [change.id for change in review.required_changes]
            duplicate_change_ids = sorted({change_id for change_id in change_ids if change_ids.count(change_id) > 1})
            if duplicate_change_ids:
                msg = f"duplicate required_change ids for reviewer {review.reviewer_id}: " + ", ".join(
                    duplicate_change_ids
                )
                raise ValueError(msg)
            for change in review.required_changes:
                proposed_by_id.setdefault(change.id, set()).add(review.reviewer_id)

        accepted_ids = [change.id for change in self.judge.material_required_changes]
        duplicate_accepted_ids = sorted({change_id for change_id in accepted_ids if accepted_ids.count(change_id) > 1})
        if duplicate_accepted_ids:
            msg = "duplicate material_required_changes ids: " + ", ".join(duplicate_accepted_ids)
            raise ValueError(msg)

        rejected_pairs = [(change.id, change.source_reviewer) for change in self.judge.rejected_required_changes]
        duplicate_rejected_pairs = sorted({pair for pair in rejected_pairs if rejected_pairs.count(pair) > 1})
        if duplicate_rejected_pairs:
            rendered = ", ".join(f"{change_id}:{reviewer_id}" for change_id, reviewer_id in duplicate_rejected_pairs)
            msg = "duplicate rejected_required_changes pairs: " + rendered
            raise ValueError(msg)

        accepted_coverage: set[tuple[str, str]] = set()
        for accepted in self.judge.material_required_changes:
            duplicate_sources = sorted(
                {source for source in accepted.source_reviewers if accepted.source_reviewers.count(source) > 1}
            )
            if duplicate_sources:
                msg = f"duplicate material_required_changes source_reviewers for {accepted.id}: " + ", ".join(
                    duplicate_sources
                )
                raise ValueError(msg)
            source_reviewers = set(accepted.source_reviewers)
            unknown_sources = source_reviewers - reviewer_id_set - {"judge"}
            if unknown_sources:
                msg = "material_required_changes source_reviewers unknown: " + ", ".join(sorted(unknown_sources))
                raise ValueError(msg)
            if accepted.id not in proposed_by_id and "judge" not in source_reviewers:
                msg = f"judge-originated material_required_changes must include judge source for {accepted.id}"
                raise ValueError(msg)
            for reviewer_id in source_reviewers - {"judge"}:
                if reviewer_id not in proposed_by_id.get(accepted.id, set()):
                    msg = f"material_required_changes source_reviewer {reviewer_id} did not propose {accepted.id}"
                    raise ValueError(msg)
            for reviewer_id in source_reviewers & proposed_by_id.get(accepted.id, set()):
                accepted_coverage.add((accepted.id, reviewer_id))

        rejected_coverage: set[tuple[str, str]] = set()
        for rejected in self.judge.rejected_required_changes:
            if rejected.id not in proposed_by_id:
                msg = f"rejected_required_changes references unknown reviewer change {rejected.id}"
                raise ValueError(msg)
            if rejected.source_reviewer not in proposed_by_id[rejected.id]:
                msg = f"rejected_required_changes source_reviewer {rejected.source_reviewer} did not propose {rejected.id}"
                raise ValueError(msg)
            rejected_coverage.add((rejected.id, rejected.source_reviewer))

        overlap = sorted(accepted_coverage & rejected_coverage)
        if overlap:
            rendered = ", ".join(f"{change_id}:{reviewer_id}" for change_id, reviewer_id in overlap)
            msg = "reviewer required_changes cannot be both accepted and rejected: " + rendered
            raise ValueError(msg)

        proposed_pairs = {
            (change_id, reviewer_id)
            for change_id, reviewer_ids_for_change in proposed_by_id.items()
            for reviewer_id in reviewer_ids_for_change
        }
        unaccounted = sorted(proposed_pairs - accepted_coverage - rejected_coverage)
        if unaccounted:
            rendered = ", ".join(f"{change_id}:{reviewer_id}" for change_id, reviewer_id in unaccounted)
            msg = "unaccounted reviewer required_changes: " + rendered
            raise ValueError(msg)
        return self


class ConvergenceLedger(StrictLedgerModel):
    """Append-only ledger for plan or execution convergence."""


    run_id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    phase: Phase
    artifact_id: str = Field(min_length=1)
    clean_rounds_required: int = Field(default=3, ge=3)
    max_rounds: int = Field(default=9, ge=1)
    rounds: tuple[ConvergenceRound, ...] = Field(default_factory=tuple)
    status: RunStatus = RunStatus.RUNNING
    blocked_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def ledger_state_is_consistent(self) -> "ConvergenceLedger":
        """Deserialized ledgers must obey the same state machine as ``with_round``."""
        clean_streak = 0
        expected_status = RunStatus.RUNNING
        expected_blocked_reason: str | None = None
        previous_round: ConvergenceRound | None = None
        if self.max_rounds < self.clean_rounds_required:
            msg = "max_rounds must be at least clean_rounds_required"
            raise ValueError(msg)
        for expected, round_ in enumerate(self.rounds, start=1):
            if round_.round_number != expected:
                msg = f"round_number must be {expected}, got {round_.round_number}"
                raise ValueError(msg)
            if previous_round is not None:
                if round_.artifact_version < previous_round.artifact_version:
                    msg = "artifact_version cannot decrease"
                    raise ValueError(msg)
                if (
                    previous_round.judge.material_required_changes
                    and round_.artifact_version <= previous_round.artifact_version
                ):
                    msg = "artifact_version must advance after material required changes"
                    raise ValueError(msg)
            if expected_status != RunStatus.RUNNING:
                msg = f"terminal {expected_status.value} round cannot be followed by more rounds"
                raise ValueError(msg)

            if round_.judge.verdict == ReviewVerdict.REJECT:
                expected_status = RunStatus.BLOCKED
                expected_blocked_reason = round_.judge.rationale
            else:
                clean_streak = clean_streak + 1 if round_.judge.clean_round else 0
                if clean_streak >= self.clean_rounds_required:
                    expected_status = RunStatus.CONVERGED
                elif expected >= self.max_rounds:
                    expected_status = RunStatus.FAILED_MAX_ROUNDS
            previous_round = round_

        if self.status != expected_status:
            msg = f"ledger status must be {expected_status.value}, got {self.status.value}"
            raise ValueError(msg)
        if self.status == RunStatus.BLOCKED:
            if not self.blocked_reason:
                msg = "BLOCKED status requires blocked_reason"
                raise ValueError(msg)
            if self.blocked_reason != expected_blocked_reason:
                msg = "blocked_reason must match final REJECT judge rationale"
                raise ValueError(msg)
        elif self.blocked_reason is not None:
            msg = "blocked_reason is only valid when status is BLOCKED"
            raise ValueError(msg)
        return self

    @staticmethod
    def _count_consecutive_clean_rounds(rounds: tuple[ConvergenceRound, ...]) -> int:
        """Count clean rounds from the end of ``rounds`` backwards."""
        count = 0
        for round_ in reversed(rounds):
            if not round_.judge.clean_round:
                break
            count += 1
        return count

    @property
    def consecutive_clean_rounds(self) -> int:
        """Count clean rounds from the end of the ledger backwards."""
        return self._count_consecutive_clean_rounds(self.rounds)

    @property
    def converged(self) -> bool:
        """True when the configured clean-round threshold is reached."""
        return self.consecutive_clean_rounds >= self.clean_rounds_required

    def with_round(self, round_: ConvergenceRound) -> "ConvergenceLedger":
        """Return a new ledger with ``round_`` appended and status updated."""
        if self.status in {RunStatus.CONVERGED, RunStatus.BLOCKED, RunStatus.FAILED_MAX_ROUNDS}:
            msg = f"cannot append rounds to terminal ledger status {self.status.value}"
            raise ValueError(msg)
        expected_round_number = len(self.rounds) + 1
        if round_.round_number != expected_round_number:
            msg = f"round_number must be {expected_round_number}, got {round_.round_number}"
            raise ValueError(msg)
        next_rounds = (*self.rounds, round_)
        if round_.judge.verdict == ReviewVerdict.REJECT:
            status = RunStatus.BLOCKED
            blocked_reason = round_.judge.rationale
        elif self._count_consecutive_clean_rounds(next_rounds) >= self.clean_rounds_required:
            status = RunStatus.CONVERGED
            blocked_reason = None
        elif len(next_rounds) >= self.max_rounds:
            status = RunStatus.FAILED_MAX_ROUNDS
            blocked_reason = None
        else:
            status = RunStatus.RUNNING
            blocked_reason = None

        data = self.model_dump()
        data.update({"rounds": next_rounds, "status": status, "blocked_reason": blocked_reason})
        return type(self).model_validate(data)
