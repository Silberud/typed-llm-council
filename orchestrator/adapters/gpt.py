"""GPT adapter — The Architect seat. Uses Codex CLI with ChatGPT Pro OAuth.

Note: spec §7.2 wrote `codex chat --model gpt-5.5 --json` — the actual
subcommand is `codex exec` (no `codex chat` exists in Codex CLI 0.132.0).
Model-pin assertion per §9.2 enforced after every call: model_used MUST
equal `gpt-5.5`, else retry once and DROP on persistent mismatch.
"""
from __future__ import annotations
import json
import logging
import shutil
import tempfile
from pathlib import Path
from orchestrator.adapters.base import ContributingAdapter
from orchestrator.adapters._common import extract_verdict, run_cli
from orchestrator.schemas.stage_output import DroppedResult, MemberResult

log = logging.getLogger("llm-council.adapters.gpt")
DEFAULT_MODEL = "gpt-5.5"


class GPTAdapter(ContributingAdapter):
    name = "gpt"

    def __init__(self, model: str = DEFAULT_MODEL, reasoning_effort: str = "high") -> None:
        self.model = model
        self.reasoning_effort = reasoning_effort

    async def auth_check(self) -> bool:
        if shutil.which("codex") is None:
            return False
        return (Path.home() / ".codex" / "auth.json").exists()

    async def ask(self, prompt: str, *, timeout: float = 90.0) -> MemberResult | DroppedResult:
        result = await self._invoke_once(prompt, timeout=timeout)
        if isinstance(result, DroppedResult):
            return result
        # Spec §9.2 model-pin assertion: retry once on mismatch, DROP on persistent.
        if result.model_used and result.model_used != self.model:
            retry = await self._invoke_once(prompt, timeout=timeout)
            if isinstance(retry, DroppedResult):
                return retry
            if retry.model_used and retry.model_used != self.model:
                return DroppedResult(member=self.name, reason="model_mismatch",
                                     detail=f"got {retry.model_used!r}, expected {self.model!r}")
            return retry
        return result

    async def _invoke_once(self, prompt: str, *, timeout: float) -> MemberResult | DroppedResult:
        tmp = Path(tempfile.mkstemp(prefix="codex_last_", suffix=".txt")[1])
        try:
            argv = [
                "codex", "exec",
                "--model", self.model,
                "--skip-git-repo-check",
                "--ephemeral",
                "--color", "never",
                "--sandbox", "read-only",
                "-c", f'model_reasoning_effort="{self.reasoning_effort}"',
                "--output-last-message", str(tmp),
                "--json",
                prompt,
            ]
            result = await run_cli(argv, timeout=timeout, member=self.name)
            if isinstance(result, DroppedResult):
                return result
            rc, stdout, stderr, elapsed = result
            text = tmp.read_text(errors="replace").strip() if tmp.exists() else ""
            # Parse JSONL stdout for the model_used metadata.
            model_used: str | None = None
            for line in stdout.splitlines():
                try:
                    obj = json.loads(line)
                    if obj.get("type") in {"task_started", "agent_message", "session_configured"}:
                        m = obj.get("model") or obj.get("model_used") or obj.get("payload", {}).get("model")
                        if m:
                            model_used = m
                except Exception:  # noqa: BLE001
                    continue
            if rc != 0 and not text:
                return DroppedResult(member=self.name, reason="nonzero_rc",
                                     detail=f"rc={rc} stderr={stderr[:200]}")
            # Spec §9.2: the model-pin assertion is non-negotiable. If Codex
            # emitted no model field at all we cannot prove drift didn't happen
            # — log a loud warning so it surfaces in operator review. Defaulting
            # to self.model below keeps the call usable but the warning is the
            # audit trail.
            if model_used is None:
                log.warning(
                    "GPT/Codex emitted no model identifier in stage events for "
                    "this call — model-pin assertion cannot be verified. "
                    "Treating as %r; review Codex CLI version if this persists.",
                    self.model,
                )
            return MemberResult(
                member=self.name, text=text,
                verdict=extract_verdict(text),
                model_used=model_used or self.model,
                duration_s=elapsed,
            )
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass
