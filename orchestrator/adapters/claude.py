"""Claude adapter — drafter (Stage 1 Self-MoA-Seq) + rotating chair (Stage 5)."""
from __future__ import annotations
import json
import shutil
from orchestrator.adapters.base import ContributingAdapter
from orchestrator.adapters._common import extract_verdict, run_cli
from orchestrator.schemas.stage_output import DroppedResult, MemberResult

# Spec said "opus-4-7"; the actual full model name is "claude-opus-4-7".
DEFAULT_MODEL = "claude-opus-4-7"


class ClaudeAdapter(ContributingAdapter):
    name = "claude"

    def __init__(self, model: str = DEFAULT_MODEL, max_budget_usd: float = 2.0) -> None:
        self.model = model
        self.max_budget_usd = max_budget_usd

    async def auth_check(self) -> bool:
        # Claude Code CLI auth is implicit (operator's running session).
        # Treat presence of the binary as the check; if absent return False.
        return shutil.which("claude") is not None

    async def ask(self, prompt: str, *, timeout: float = 90.0) -> MemberResult | DroppedResult:
        argv = [
            "claude",
            "--model", self.model,
            "--print",
            "--output-format", "json",
            "--max-budget-usd", str(self.max_budget_usd),
        ]
        result = await run_cli(argv, stdin=prompt, timeout=timeout, member=self.name)
        if isinstance(result, DroppedResult):
            return result
        rc, stdout, stderr, elapsed = result
        if rc != 0:
            return DroppedResult(member=self.name, reason="nonzero_rc",
                                 detail=f"rc={rc} stderr={stderr[:200]}")
        # Claude Code --output-format json: result body in a "result" or "text" field.
        text: str = ""
        model_used: str | None = None
        try:
            obj = json.loads(stdout)
            for key in ("result", "text", "output", "content", "response"):
                if key in obj and isinstance(obj[key], str):
                    text = obj[key]
                    break
            if not text and isinstance(obj.get("messages"), list):
                # Concatenate assistant messages if present
                text = "\n".join(
                    m.get("content", "") for m in obj["messages"]
                    if m.get("role") == "assistant" and isinstance(m.get("content"), str)
                )
            model_used = obj.get("model") or obj.get("model_used")
        except json.JSONDecodeError:
            text = stdout
        return MemberResult(
            member=self.name, text=text.strip(),
            verdict=extract_verdict(text),
            model_used=model_used or self.model,
            duration_s=elapsed,
        )
