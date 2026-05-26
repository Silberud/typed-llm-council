"""Unit tests for the Phase E.2 real CoVe comparator.

Mocks the Claude call. The live-Claude version is in tests/_live/.
"""
import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.schemas.stage_output import VerifierAnswer
from orchestrator.services.comparator import (
    compare_answers_real, _parse_judgments, _strip_markdown_fences,
)


def _ans(text: str, conf: float = 0.9) -> VerifierAnswer:
    return VerifierAnswer(answer=text, confidence=conf, confidence_parsed=True)


def _mock_claude(judgments_json: str):
    """Patch ClaudeAdapter.ask to return a fake MemberResult with given JSON.

    ClaudeAdapter is locally imported in comparator.compare_answers_real,
    so we patch at the source location (orchestrator.adapters.claude).
    """
    from orchestrator.schemas.stage_output import MemberResult
    fake = MemberResult(member="claude", text=judgments_json)
    return patch(
        "orchestrator.adapters.claude.ClaudeAdapter.ask",
        AsyncMock(return_value=fake),
    )


# ---------- parser unit tests ----------

def test_parse_supports():
    js = '[{"index":0,"judgment":"SUPPORT","rationale":"matches draft"},' \
         ' {"index":1,"judgment":"CONTRADICT","rationale":"disagrees"}]'
    out = _parse_judgments(js, n_expected=2)
    assert len(out) == 2
    assert out[0].judgment == "SUPPORT"
    assert out[1].judgment == "CONTRADICT"


def test_parse_strips_markdown_fences():
    js = '```json\n[{"index":0,"judgment":"SUPPORT","rationale":"ok"}]\n```'
    out = _parse_judgments(js, n_expected=1)
    assert out[0].judgment == "SUPPORT"


def test_parse_malformed_json_falls_back():
    out = _parse_judgments("definitely not json {[}", n_expected=3)
    assert len(out) == 3
    assert all(j.judgment == "NOT_RELATE" for j in out)
    assert all(j.rationale == "parse_fallback" for j in out)


def test_parse_partial_returns_uses_fallback_for_missing():
    js = '[{"index":0,"judgment":"SUPPORT","rationale":"ok"}]'
    out = _parse_judgments(js, n_expected=3)
    assert out[0].judgment == "SUPPORT"
    assert out[1].judgment == "NOT_RELATE" and out[1].rationale == "parse_fallback"
    assert out[2].judgment == "NOT_RELATE" and out[2].rationale == "parse_fallback"


def test_parse_rejects_invalid_judgment_label():
    js = '[{"index":0,"judgment":"MAYBE","rationale":"weird"}]'
    out = _parse_judgments(js, n_expected=1)
    # Invalid label is dropped → fallback used
    assert out[0].rationale == "parse_fallback"


def test_strip_markdown_fences():
    assert _strip_markdown_fences("```json\n[]\n```") == "[]"
    assert _strip_markdown_fences("[]") == "[]"
    assert _strip_markdown_fences("```\n[]\n```") == "[]"


# ---------- compare_answers_real integration (with mocked Claude) ----------

def test_compare_answers_real_all_support():
    js = json.dumps([
        {"index": 0, "judgment": "SUPPORT", "rationale": "Confirms."},
        {"index": 1, "judgment": "SUPPORT", "rationale": "Confirms."},
    ])
    with _mock_claude(js):
        out = asyncio.run(compare_answers_real(
            draft_text="Draft.",
            questions=["Q1", "Q2"],
            verifier_answers=[_ans("A1"), _ans("A2")],
        ))
    assert out["agreements"] == 2
    assert out["disagreements"] == 0
    assert out["comparator_mode"] == "real_claude_batched"


def test_compare_answers_real_mixed():
    js = json.dumps([
        {"index": 0, "judgment": "SUPPORT", "rationale": "Confirms."},
        {"index": 1, "judgment": "CONTRADICT", "rationale": "Refutes."},
        {"index": 2, "judgment": "NOT_RELATE", "rationale": "Off-topic."},
    ])
    with _mock_claude(js):
        out = asyncio.run(compare_answers_real(
            draft_text="Draft.",
            questions=["Q1", "Q2", "Q3"],
            verifier_answers=[_ans("A1"), _ans("A2"), _ans("A3")],
        ))
    assert out["agreements"] == 1
    assert out["disagreements"] == 1
    assert any("Refutes" in f for f in out["flagged"])
    assert any("Off-topic" in f for f in out["flagged"])


def test_compare_answers_real_handles_empty_input():
    out = asyncio.run(compare_answers_real(
        draft_text="Draft.", questions=[], verifier_answers=[],
    ))
    assert out["agreements"] == 0
    assert out["disagreements"] == 0
    assert out["judgments"] == []


def test_compare_answers_real_length_mismatch_raises():
    with pytest.raises(ValueError, match="same length"):
        asyncio.run(compare_answers_real(
            draft_text="Draft.",
            questions=["Q1", "Q2"],
            verifier_answers=[_ans("A1")],
        ))


# ---------- Stage 3 dispatch behaviour ----------

def test_dispatcher_uses_placeholder_by_default():
    """Without [stages.stage3] comparator_mode = 'real', dispatch goes to placeholder."""
    from orchestrator.stages.stage3_verification import compare_answers
    with patch(
        "orchestrator.stages.stage3_verification._comparator_mode_from_config",
        return_value="placeholder",
    ):
        out = asyncio.run(compare_answers(
            draft_text="Draft.",
            questions=["Q1"],
            verifier_answers=[_ans("A1", conf=0.9)],
        ))
    assert out["comparator_mode"] == "placeholder_confidence_threshold"


def test_dispatcher_uses_real_when_configured():
    from orchestrator.stages.stage3_verification import compare_answers
    js = json.dumps([{"index": 0, "judgment": "SUPPORT", "rationale": "ok"}])
    with patch(
        "orchestrator.stages.stage3_verification._comparator_mode_from_config",
        return_value="real",
    ), _mock_claude(js):
        out = asyncio.run(compare_answers(
            draft_text="Draft.",
            questions=["Q1"],
            verifier_answers=[_ans("A1")],
        ))
    assert out["comparator_mode"] == "real_claude_batched"
    assert out["agreements"] == 1


def test_dispatcher_falls_back_to_placeholder_on_real_failure():
    """If real comparator raises, dispatch logs and falls back to placeholder."""
    from orchestrator.stages.stage3_verification import compare_answers
    with patch(
        "orchestrator.stages.stage3_verification._comparator_mode_from_config",
        return_value="real",
    ), patch(
        "orchestrator.adapters.claude.ClaudeAdapter.ask",
        AsyncMock(side_effect=RuntimeError("simulated claude failure")),
    ):
        out = asyncio.run(compare_answers(
            draft_text="Draft.",
            questions=["Q1"],
            verifier_answers=[_ans("A1", conf=0.9)],
        ))
    # Fell back to placeholder
    assert out["comparator_mode"] == "placeholder_confidence_threshold"
