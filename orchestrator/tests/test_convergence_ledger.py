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
                source_reviewers=["skeptic"],
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


def round_with(number: int, decision: JudgeDecision) -> ConvergenceRound:
    return ConvergenceRound(
        round_number=number,
        artifact_version=number,
        reviews=[approve_review(optional=bool(decision.optional_suggestions))],
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
    with pytest.raises(ValidationError, match="converged ledger status must be CONVERGED"):
        ConvergenceLedger(
            run_id="run-7",
            goal="Reject mismatched converged status",
            phase=Phase.PLAN,
            artifact_id="plan.md",
            rounds=clean_rounds,
            status=RunStatus.RUNNING,
        )
