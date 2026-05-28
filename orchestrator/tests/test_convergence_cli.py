"""Tests for local convergence ledger CLI validation/replay commands."""
from __future__ import annotations

import json

import pytest

from orchestrator.schemas.convergence import (
    ConvergenceLedger,
    ConvergenceRound,
    CouncilReview,
    JudgeDecision,
    Phase,
    ReviewVerdict,
    RunStatus,
)
from orchestrator.supervisor import main


def _approve_review(reviewer_id: str = "skeptic") -> CouncilReview:
    return CouncilReview(
        reviewer_id=reviewer_id,
        provider="gpt",
        role="skeptic",
        verdict=ReviewVerdict.APPROVE,
        required_changes=[],
        optional_suggestions=[],
        main_risk="none",
        evidence_checked=["pytest"],
        blind_spots_or_assumptions=[],
        confidence=90,
    )


def _clean_decision() -> JudgeDecision:
    return JudgeDecision(
        verdict=ReviewVerdict.APPROVE,
        material_required_changes=[],
        rejected_required_changes=[],
        optional_suggestions=[],
        dissent_remaining=[],
        evidence_gates_passed=True,
        clean_round=True,
        confidence=95,
        rationale="No material required changes remain.",
    )


def _round(number: int) -> ConvergenceRound:
    return ConvergenceRound(
        round_number=number,
        artifact_version=1,
        reviews=[_approve_review()],
        judge=_clean_decision(),
    )


def _converged_ledger() -> ConvergenceLedger:
    ledger = ConvergenceLedger(
        run_id="cli-run",
        goal="Validate and replay a ledger file",
        phase=Phase.PLAN,
        artifact_id="plan.md",
    )
    return ledger.with_round(_round(1)).with_round(_round(2)).with_round(_round(3))


def test_converge_validate_accepts_valid_ledger(tmp_path, capsys, monkeypatch) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(_converged_ledger().model_dump_json(), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["council", "converge", "validate", str(ledger_path)])
    monkeypatch.setattr("orchestrator.supervisor.load_config", lambda: pytest.fail("converge must not load config"))
    monkeypatch.setattr("orchestrator.supervisor.build_adapters", lambda config: pytest.fail("converge must not build adapters"))

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "valid": True,
        "run_id": "cli-run",
        "phase": "PLAN",
        "status": "CONVERGED",
        "rounds": 3,
        "consecutive_clean_rounds": 3,
    }


def test_converge_validate_rejects_invalid_ledger(tmp_path, capsys, monkeypatch) -> None:
    ledger_path = tmp_path / "ledger.json"
    data = _converged_ledger().model_dump()
    data["status"] = RunStatus.RUNNING.value
    ledger_path.write_text(json.dumps(data), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["council", "converge", "validate", str(ledger_path)])

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert "ledger status must be CONVERGED, got RUNNING" in payload["error"]


def test_converge_replay_prints_round_trace(tmp_path, capsys, monkeypatch) -> None:
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(_converged_ledger().model_dump_json(), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["council", "converge", "replay", str(ledger_path)])

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 0
    output = capsys.readouterr().out
    assert "round=1 artifact_version=1 verdict=APPROVE clean=True" in output
    assert "round=3 artifact_version=1 verdict=APPROVE clean=True" in output
    assert "final status=CONVERGED consecutive_clean_rounds=3" in output
