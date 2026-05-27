"""Tests for deterministic Convergence Council Protocol ledger invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.schemas.convergence import (
    ConvergenceLedger,
    ConvergenceRound,
    CouncilReview,
    JudgeDecision,
    MaterialRequiredChange,
    OptionalSuggestion,
    Phase,
    RejectedRequiredChange,
    RemainingDissent,
    ReviewRequiredChange,
    ReviewVerdict,
    RunStatus,
)


def approve_review(reviewer_id: str = "skeptic", *, optional: bool = False) -> CouncilReview:
    return CouncilReview(
        reviewer_id=reviewer_id,
        provider="gpt",
        role="skeptic",
        verdict=ReviewVerdict.APPROVE,
        required_changes=[],
        optional_suggestions=[
            OptionalSuggestion(
                description="Polish phrasing later.",
                rationale="Helpful but not material.",
            )
        ]
        if optional
        else [],
        main_risk="none",
        evidence_checked=["pytest orchestrator/tests/test_convergence_ledger.py -q"],
        blind_spots_or_assumptions=[],
        confidence=88,
    )


def clean_decision(*, optional: bool = False) -> JudgeDecision:
    return JudgeDecision(
        verdict=ReviewVerdict.APPROVE,
        material_required_changes=[],
        rejected_required_changes=[],
        optional_suggestions=[
            OptionalSuggestion(description="Add richer docs later", rationale="Non-blocking")
        ]
        if optional
        else [],
        dissent_remaining=[],
        evidence_gates_passed=True,
        clean_round=True,
        confidence=95,
        rationale="No material required changes remain.",
    )


def dirty_decision() -> JudgeDecision:
    return JudgeDecision(
        verdict=ReviewVerdict.MODIFY,
        material_required_changes=[
            MaterialRequiredChange(
                id="REQ-1",
                source_reviewers=["judge"],
                description="Add an invariant test before claiming convergence.",
                acceptance_criteria="A failing test proves the invariant.",
            )
        ],
        rejected_required_changes=[],
        optional_suggestions=[],
        dissent_remaining=[],
        evidence_gates_passed=True,
        clean_round=False,
        confidence=80,
        rationale="A material gap remains.",
    )


def reject_decision() -> JudgeDecision:
    return JudgeDecision(
        verdict=ReviewVerdict.REJECT,
        material_required_changes=[
            MaterialRequiredChange(
                id="REQ-BLOCK",
                source_reviewers=["judge"],
                description="The artifact is not salvageable in this loop.",
                acceptance_criteria="Start a new artifact with a narrower scope.",
            )
        ],
        rejected_required_changes=[],
        optional_suggestions=[],
        dissent_remaining=[],
        evidence_gates_passed=True,
        clean_round=False,
        confidence=70,
        rationale="Judge rejected the artifact as blocked.",
    )


def review_with_required_change(reviewer_id: str = "skeptic", change_id: str = "REQ-ACCOUNT") -> CouncilReview:
    return CouncilReview(
        reviewer_id=reviewer_id,
        provider="gpt",
        role="skeptic",
        verdict=ReviewVerdict.MODIFY,
        required_changes=[
            ReviewRequiredChange(
                id=change_id,
                description="The judge must account for this requested change.",
                evidence_or_reason="Otherwise material reviewer objections can disappear.",
            )
        ],
        optional_suggestions=[],
        main_risk="Dropped required change.",
        evidence_checked=["diff"],
        blind_spots_or_assumptions=[],
        confidence=91,
    )


def round_with(number: int, decision: JudgeDecision) -> ConvergenceRound:
    return ConvergenceRound(
        round_number=number,
        artifact_version=number,
        reviews=[approve_review(optional=bool(decision.optional_suggestions))],
        judge=decision,
    )


def round_with_review(number: int, review: CouncilReview, decision: JudgeDecision) -> ConvergenceRound:
    return ConvergenceRound(
        round_number=number,
        artifact_version=number,
        reviews=[review],
        judge=decision,
    )


def test_optional_suggestions_preserved_without_resetting_clean_rounds() -> None:
    ledger = ConvergenceLedger(
        run_id="run-1",
        goal="Converge a plan",
        phase=Phase.PLAN,
        artifact_id="plan.md",
    )

    ledger = ledger.with_round(round_with(1, clean_decision(optional=True)))
    ledger = ledger.with_round(round_with(2, clean_decision(optional=True)))
    ledger = ledger.with_round(round_with(3, clean_decision(optional=True)))

    assert ledger.consecutive_clean_rounds == 3
    assert ledger.status is RunStatus.CONVERGED
    assert ledger.rounds[0].judge.optional_suggestions[0].description == "Add richer docs later"


def test_material_required_changes_reset_consecutive_clean_rounds() -> None:
    ledger = ConvergenceLedger(
        run_id="run-2",
        goal="Converge execution evidence",
        phase=Phase.EXECUTION,
        artifact_id="evidence.json",
    )

    ledger = ledger.with_round(round_with(1, clean_decision()))
    ledger = ledger.with_round(round_with(2, clean_decision()))
    ledger = ledger.with_round(round_with(3, dirty_decision()))

    assert ledger.consecutive_clean_rounds == 0
    assert ledger.status is RunStatus.RUNNING


def test_judge_must_explain_rejected_required_changes() -> None:
    rejected = RejectedRequiredChange(
        id="REQ-2",
        source_reviewer="architect",
        reason_rejected_as_non_material="Already covered by existing schema tests.",
    )

    decision = clean_decision().model_copy(update={"rejected_required_changes": [rejected]})

    assert decision.rejected_required_changes[0].reason_rejected_as_non_material


def test_confidence_caps_apply_to_missing_evidence_and_material_dissent() -> None:
    with pytest.raises(ValidationError, match="confidence 90 exceeds cap 60"):
        JudgeDecision(
            verdict=ReviewVerdict.APPROVE,
            material_required_changes=[],
            rejected_required_changes=[],
            optional_suggestions=[],
            dissent_remaining=[],
            evidence_gates_passed=False,
            clean_round=False,
            confidence=90,
            rationale="Cannot be highly confident without evidence gates.",
        )

    with pytest.raises(ValidationError, match="confidence 90 exceeds cap 75"):
        JudgeDecision(
            verdict=ReviewVerdict.MODIFY,
            material_required_changes=[],
            rejected_required_changes=[],
            optional_suggestions=[],
            dissent_remaining=[
                RemainingDissent(
                    reviewer_id="skeptic",
                    summary="The evidence gate is under-specified.",
                    material=True,
                )
            ],
            evidence_gates_passed=True,
            clean_round=False,
            confidence=90,
            rationale="Material dissent remains unresolved.",
        )


def test_max_rounds_without_convergence_enters_failed_state() -> None:
    ledger = ConvergenceLedger(
        run_id="run-3",
        goal="Converge stubborn artifact",
        phase=Phase.PLAN,
        artifact_id="plan.md",
        clean_rounds_required=3,
        max_rounds=2,
    )

    ledger = ledger.with_round(round_with(1, dirty_decision()))
    ledger = ledger.with_round(round_with(2, dirty_decision()))

    assert ledger.status is RunStatus.FAILED_MAX_ROUNDS


def test_reviewer_verdicts_require_material_change_consistency() -> None:
    with pytest.raises(ValidationError, match="APPROVE reviews cannot include required_changes"):
        CouncilReview(
            reviewer_id="skeptic",
            provider="gpt",
            role="skeptic",
            verdict=ReviewVerdict.APPROVE,
            required_changes=[
                ReviewRequiredChange(
                    id="REQ-3",
                    description="Cannot approve while requiring a change.",
                    evidence_or_reason="Contradictory verdict.",
                )
            ],
            optional_suggestions=[],
            main_risk="Contradictory verdict.",
            evidence_checked=[],
            blind_spots_or_assumptions=[],
            confidence=70,
        )

    with pytest.raises(ValidationError, match="MODIFY/REJECT reviews must include"):
        CouncilReview(
            reviewer_id="judge",
            provider="claude",
            role="judge",
            verdict=ReviewVerdict.MODIFY,
            required_changes=[],
            optional_suggestions=[],
            main_risk="Missing material change detail.",
            evidence_checked=[],
            blind_spots_or_assumptions=[],
            confidence=70,
        )


def test_ledger_rejects_out_of_sequence_round_numbers() -> None:
    ledger = ConvergenceLedger(
        run_id="run-4",
        goal="Converge in order",
        phase=Phase.PLAN,
        artifact_id="plan.md",
    )

    with pytest.raises(ValueError, match="round_number must be 1"):
        ledger.with_round(round_with(2, clean_decision()))


def test_terminal_ledgers_are_append_closed() -> None:
    ledger = ConvergenceLedger(
        run_id="run-5",
        goal="Converge once",
        phase=Phase.PLAN,
        artifact_id="plan.md",
        clean_rounds_required=1,
    ).with_round(round_with(1, clean_decision()))

    assert ledger.status is RunStatus.CONVERGED
    with pytest.raises(ValueError, match="cannot append rounds to terminal ledger status CONVERGED"):
        ledger.with_round(round_with(2, clean_decision()))


def test_required_text_fields_are_non_empty() -> None:
    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        RejectedRequiredChange(
            id="REQ-4",
            source_reviewer="architect",
            reason_rejected_as_non_material="",
        )


def test_deserialized_ledger_enforces_round_sequence_and_status() -> None:
    with pytest.raises(ValidationError, match="round_number must be 1"):
        ConvergenceLedger(
            run_id="run-6",
            goal="Reject out-of-order stored rounds",
            phase=Phase.PLAN,
            artifact_id="plan.md",
            rounds=[round_with(2, clean_decision())],
        )

    clean_rounds = [round_with(1, clean_decision()), round_with(2, clean_decision()), round_with(3, clean_decision())]
    with pytest.raises(ValidationError, match="ledger status must be CONVERGED, got RUNNING"):
        ConvergenceLedger(
            run_id="run-7",
            goal="Reject mismatched converged status",
            phase=Phase.PLAN,
            artifact_id="plan.md",
            rounds=clean_rounds,
            status=RunStatus.RUNNING,
        )


def test_with_round_revalidates_resulting_ledger() -> None:
    ledger = ConvergenceLedger(
        run_id="run-8",
        goal="Prove append path cannot bypass validators",
        phase=Phase.PLAN,
        artifact_id="plan.md",
        max_rounds=1,
    )

    next_ledger = ledger.with_round(round_with(1, dirty_decision()))

    assert next_ledger.status is RunStatus.FAILED_MAX_ROUNDS
    with pytest.raises(ValidationError, match="ledger status must be FAILED_MAX_ROUNDS, got RUNNING"):
        ConvergenceLedger.model_validate(
            next_ledger.model_dump() | {"status": RunStatus.RUNNING.value}
        )


def test_reviewer_required_changes_must_be_accounted_for_by_judge() -> None:
    review = review_with_required_change(change_id="REQ-ACCOUNT")
    dropped = clean_decision().model_copy(update={"clean_round": False, "confidence": 80})

    with pytest.raises(ValidationError, match="unaccounted reviewer required_changes"):
        round_with_review(1, review, dropped)

    accepted = dirty_decision().model_copy(
        update={
            "material_required_changes": [
                MaterialRequiredChange(
                    id="REQ-ACCOUNT",
                    source_reviewers=["skeptic"],
                    description="The judge accepted the reviewer's required change.",
                    acceptance_criteria="The change is present in material_required_changes.",
                )
            ]
        }
    )
    assert round_with_review(1, review, accepted).judge.material_required_changes[0].id == "REQ-ACCOUNT"

    rejected = clean_decision().model_copy(
        update={
            "clean_round": False,
            "confidence": 80,
            "rejected_required_changes": [
                RejectedRequiredChange(
                    id="REQ-ACCOUNT",
                    source_reviewer="skeptic",
                    reason_rejected_as_non_material="Already covered by another accepted change.",
                )
            ],
        }
    )
    assert round_with_review(1, review, rejected).judge.rejected_required_changes[0].id == "REQ-ACCOUNT"


def test_blocked_status_is_reachable_and_requires_reason() -> None:
    ledger = ConvergenceLedger(
        run_id="run-9",
        goal="Reject blocked artifact",
        phase=Phase.EXECUTION,
        artifact_id="evidence.json",
    )

    blocked = ledger.with_round(round_with(1, reject_decision()))

    assert blocked.status is RunStatus.BLOCKED
    assert blocked.blocked_reason == "Judge rejected the artifact as blocked."
    with pytest.raises(ValueError, match="cannot append rounds to terminal ledger status BLOCKED"):
        blocked.with_round(round_with(2, clean_decision()))

    with pytest.raises(ValidationError, match="BLOCKED status requires blocked_reason"):
        ConvergenceLedger(
            run_id="run-10",
            goal="Invalid blocked state",
            phase=Phase.PLAN,
            artifact_id="plan.md",
            rounds=[round_with(1, reject_decision())],
            status=RunStatus.BLOCKED,
        )


def test_duplicate_required_change_ids_need_each_reviewer_accounted() -> None:
    alice = review_with_required_change(reviewer_id="alice", change_id="REQ-DUP")
    bob = review_with_required_change(reviewer_id="bob", change_id="REQ-DUP")
    only_alice_accounted = dirty_decision().model_copy(
        update={
            "material_required_changes": [
                MaterialRequiredChange(
                    id="REQ-DUP",
                    source_reviewers=("alice",),
                    description="Only Alice's copy of the duplicate id was accepted.",
                    acceptance_criteria="Bob must still be accepted or rejected separately.",
                )
            ]
        }
    )

    with pytest.raises(ValidationError, match="unaccounted reviewer required_changes: REQ-DUP:bob"):
        ConvergenceRound(
            round_number=1,
            artifact_version=1,
            reviews=[alice, bob],
            judge=only_alice_accounted,
        )

    both_accounted = dirty_decision().model_copy(
        update={
            "material_required_changes": [
                MaterialRequiredChange(
                    id="REQ-DUP",
                    source_reviewers=["alice", "bob"],
                    description="Both duplicate-id proposers are accepted.",
                    acceptance_criteria="Every reviewer/id pair is covered.",
                )
            ]
        }
    )
    assert ConvergenceRound(round_number=1, artifact_version=1, reviews=[alice, bob], judge=both_accounted)


def test_deserialized_ledger_rejects_rounds_after_terminal_prefixes() -> None:
    with pytest.raises(ValidationError, match="terminal CONVERGED round cannot be followed"):
        ConvergenceLedger(
            run_id="run-11",
            goal="Reject extra rounds after convergence",
            phase=Phase.PLAN,
            artifact_id="plan.md",
            clean_rounds_required=1,
            rounds=[round_with(1, clean_decision()), round_with(2, dirty_decision())],
            status=RunStatus.FAILED_MAX_ROUNDS,
        )

    with pytest.raises(ValidationError, match="terminal BLOCKED round cannot be followed"):
        ConvergenceLedger(
            run_id="run-12",
            goal="Reject extra rounds after blocked verdict",
            phase=Phase.PLAN,
            artifact_id="plan.md",
            rounds=[round_with(1, reject_decision()), round_with(2, clean_decision())],
            status=RunStatus.BLOCKED,
            blocked_reason="Judge rejected the artifact as blocked.",
        )


def test_judge_decision_verdict_must_match_material_state() -> None:
    with pytest.raises(ValidationError, match="APPROVE judge decisions cannot include material_required_changes"):
        JudgeDecision(
            verdict=ReviewVerdict.APPROVE,
            material_required_changes=[
                MaterialRequiredChange(
                    id="REQ-BAD",
                    source_reviewers=["judge"],
                    description="Contradicts APPROVE.",
                    acceptance_criteria="Do not allow hidden blockers in APPROVE.",
                )
            ],
            rejected_required_changes=[],
            optional_suggestions=[],
            dissent_remaining=[],
            evidence_gates_passed=True,
            clean_round=False,
            confidence=80,
            rationale="Approve cannot carry material blockers.",
        )

    with pytest.raises(ValidationError, match="MODIFY/REJECT judge decisions require material changes or material dissent"):
        JudgeDecision(
            verdict=ReviewVerdict.REJECT,
            material_required_changes=[],
            rejected_required_changes=[],
            optional_suggestions=[],
            dissent_remaining=[],
            evidence_gates_passed=True,
            clean_round=False,
            confidence=70,
            rationale="Reject without material reason is contradictory.",
        )


def test_round_rejects_duplicate_reviewer_ids_and_duplicate_change_ids() -> None:
    first = review_with_required_change(reviewer_id="dup", change_id="REQ-A")
    second = review_with_required_change(reviewer_id="dup", change_id="REQ-B")
    with pytest.raises(ValidationError, match="duplicate reviewer_id values: dup"):
        ConvergenceRound(
            round_number=1,
            artifact_version=1,
            reviews=[first, second],
            judge=dirty_decision(),
        )

    duplicate_change_review = CouncilReview(
        reviewer_id="skeptic",
        provider="gpt",
        role="skeptic",
        verdict=ReviewVerdict.MODIFY,
        required_changes=[
            ReviewRequiredChange(
                id="REQ-DUP-IN-REVIEW",
                description="First copy.",
                evidence_or_reason="Duplicate ids collapse accounting.",
            ),
            ReviewRequiredChange(
                id="REQ-DUP-IN-REVIEW",
                description="Second copy.",
                evidence_or_reason="Duplicate ids collapse accounting.",
            ),
        ],
        optional_suggestions=[],
        main_risk="Duplicate change ids.",
        evidence_checked=["diff"],
        blind_spots_or_assumptions=[],
        confidence=90,
    )
    with pytest.raises(ValidationError, match="duplicate required_change ids for reviewer skeptic"):
        round_with_review(1, duplicate_change_review, dirty_decision())


def test_material_required_change_sources_must_match_proposers() -> None:
    review = review_with_required_change(reviewer_id="alice", change_id="REQ-SOURCE")
    wrong_source = dirty_decision().model_copy(
        update={
            "material_required_changes": [
                MaterialRequiredChange(
                    id="REQ-SOURCE",
                    source_reviewers=["alice", "bob"],
                    description="Bob did not propose this id.",
                    acceptance_criteria="Only proposers may be cited as sources.",
                )
            ]
        }
    )

    with pytest.raises(ValidationError, match="material_required_changes source_reviewers unknown: bob"):
        round_with_review(1, review, wrong_source)

    judge_originated = dirty_decision().model_copy(
        update={
            "material_required_changes": [
                MaterialRequiredChange(
                    id="REQ-JUDGE",
                    source_reviewers=["judge"],
                    description="Judge-promoted material change.",
                    acceptance_criteria="Reserved judge provenance is explicit.",
                )
            ]
        }
    )
    assert round_with(1, judge_originated).judge.material_required_changes[0].source_reviewers == ("judge",)


def test_reviewer_required_change_cannot_be_both_accepted_and_rejected() -> None:
    review = review_with_required_change(reviewer_id="alice", change_id="REQ-CONFLICT")
    contradictory = dirty_decision().model_copy(
        update={
            "material_required_changes": [
                MaterialRequiredChange(
                    id="REQ-CONFLICT",
                    source_reviewers=("alice",),
                    description="The judge accepted Alice's change.",
                    acceptance_criteria="It must be implemented before convergence.",
                )
            ],
            "rejected_required_changes": [
                RejectedRequiredChange(
                    id="REQ-CONFLICT",
                    source_reviewer="alice",
                    reason_rejected_as_non_material="The same pair cannot also be rejected.",
                )
            ],
        }
    )

    with pytest.raises(ValidationError, match="cannot be both accepted and rejected: REQ-CONFLICT:alice"):
        round_with_review(1, review, contradictory)


def test_ledger_records_are_immutable_after_validation() -> None:
    decision = clean_decision()
    with pytest.raises(ValidationError, match="Instance is frozen"):
        decision.confidence = 999

    ledger = ConvergenceLedger(
        run_id="run-13",
        goal="Keep terminal state immutable",
        phase=Phase.PLAN,
        artifact_id="plan.md",
        clean_rounds_required=1,
    ).with_round(round_with(1, clean_decision()))

    assert ledger.status is RunStatus.CONVERGED
    with pytest.raises(AttributeError):
        getattr(ledger.rounds, "append")(round_with(2, clean_decision()))
