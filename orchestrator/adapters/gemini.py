"""Gemini adapter — The Researcher seat."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from orchestrator.adapters.base import ContributingAdapter
from orchestrator.adapters._common import extract_verdict, run_cli
from orchestrator.schemas.stage_output import DroppedResult, MemberResult

# Spec wrote "gemini-3.1-pro"; current API id is "gemini-3.1-pro-preview" (until GA).
DEFAULT_MODEL = "gemini-3.1-pro-preview"


class GeminiAdapter(ContributingAdapter):
    name = "gemini"

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    async def auth_check(self) -> bool:
        if shutil.which("gemini") is None:
            return False
        # gemini-cli stores OAuth creds in ~/.gemini/oauth_creds.json
        return (Path.home() / ".gemini" / "oauth_creds.json").exists()

    async def ask(self, prompt: str, *, timeout: float = 90.0) -> MemberResult | DroppedResult:
        # Spec said --prompt-file; actual flag is -p (or stdin).
        # Empirical findings:
        #  - `-p "" + stdin` hangs the CLI (Phase γ, 2026-05-24).
        #  - Bare invocation reads prompt from stdin cleanly (probe 2026-05-25)
        #    — switched here to keep prompt content off argv (Hermes #4
        #    privacy finding). The `-p` value is intentionally omitted.
        #  - Without --skip-trust the CLI exits rc=55 in non-trusted dirs.
        #  - gemini-3.1-pro-preview rate-limits aggressively; gemini-cli
        #    handles it with exponential backoff (~10s, 20s, 40s, 80s…), so
        #    we need a timeout that gives backoff room — default ≥180s.
        argv = [
            "gemini",
            "--model", self.model,
            "--skip-trust",
            "--output-format", "json",
        ]
        # Pass the prompt via stdin instead of argv -p. Hermes finding #4:
        # argv is visible to ps/audit logs; stdin is per-process-private.
        result = await run_cli(argv, stdin=prompt, timeout=timeout, member=self.name)
        if isinstance(result, DroppedResult):
            return result
        rc, stdout, stderr, elapsed = result
        if rc != 0:
            return DroppedResult(member=self.name, reason="nonzero_rc",
                                 detail=f"rc={rc} stderr={stderr[:200]}")
        text: str = ""
        model_used: str | None = None
        try:
            obj = json.loads(stdout)
            for key in ("response", "text", "result", "output", "content"):
                if key in obj and isinstance(obj[key], str):
                    text = obj[key]
                    break
            model_used = obj.get("model") or obj.get("model_used")
        except json.JSONDecodeError:
            text = stdout
        return MemberResult(
            member=self.name, text=text.strip(),
            verdict=extract_verdict(text),
            model_used=model_used or self.model,
            duration_s=elapsed,
        )
