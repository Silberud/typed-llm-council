"""Config parsing and packaging regression tests."""
from __future__ import annotations

import subprocess
import sys
import zipfile


def test_comparator_mode_reads_real_from_config(monkeypatch):
    from orchestrator.stages.stage3_verification import _comparator_mode_from_config

    monkeypatch.setattr(
        "orchestrator.supervisor.load_config",
        lambda: {"stages": {"stage3": {"comparator_mode": "real"}}},
    )

    assert _comparator_mode_from_config() == "real"


def test_comparator_mode_reads_placeholder_from_config(monkeypatch):
    from orchestrator.stages.stage3_verification import _comparator_mode_from_config

    monkeypatch.setattr(
        "orchestrator.supervisor.load_config",
        lambda: {"stages": {"stage3": {"comparator_mode": "placeholder"}}},
    )

    assert _comparator_mode_from_config() == "placeholder"


def test_comparator_mode_falls_back_for_missing_invalid_or_broken_config(monkeypatch):
    from orchestrator.stages.stage3_verification import _comparator_mode_from_config

    monkeypatch.setattr("orchestrator.supervisor.load_config", lambda: {})
    assert _comparator_mode_from_config() == "placeholder"

    monkeypatch.setattr(
        "orchestrator.supervisor.load_config",
        lambda: {"stages": {"stage3": {"comparator_mode": "surprise"}}},
    )
    assert _comparator_mode_from_config() == "placeholder"

    def _boom():
        raise RuntimeError("config unavailable")

    monkeypatch.setattr("orchestrator.supervisor.load_config", _boom)
    assert _comparator_mode_from_config() == "placeholder"


def test_wheel_includes_default_config(tmp_path):
    """A normal wheel install must include the default config used by supervisor.py."""
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(dist_dir),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as zf:
        assert "orchestrator/config.toml" in zf.namelist()
