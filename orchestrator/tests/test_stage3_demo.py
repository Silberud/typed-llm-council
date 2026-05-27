"""Regression tests for the public Stage 3 structural demo."""
from __future__ import annotations

import pytest

from examples import stage3_verification_demo


@pytest.mark.asyncio
async def test_stage3_demo_forces_placeholder_comparator(tmp_path, monkeypatch, capsys):
    """The demo promises no real LLM calls, even if local config opts into real mode."""
    cfg = tmp_path / "config.toml"
    cfg.write_text('[stages.stage3]\ncomparator_mode = "real"\n')
    monkeypatch.setenv("LLM_COUNCIL_CONFIG", str(cfg))

    async def _real_comparator_must_not_run(*args, **kwargs):  # pragma: no cover - fail path
        raise AssertionError("demo attempted to call the real Claude comparator")

    monkeypatch.setattr(
        "orchestrator.services.comparator.compare_answers_real",
        _real_comparator_must_not_run,
    )

    rc = await stage3_verification_demo.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "comparator_mode: placeholder_confidence_threshold" in out
    assert "no real LLM calls" in out
