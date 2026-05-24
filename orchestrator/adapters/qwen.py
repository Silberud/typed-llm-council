"""Qwen adapter — The Analyst seat (Ollama Queue A). DRIFTJudge uses Queue B."""
from __future__ import annotations
import asyncio
import time
import httpx
from orchestrator.adapters.base import ContributingAdapter
from orchestrator.adapters._common import extract_verdict
from orchestrator.schemas.stage_output import DroppedResult, MemberResult

DEFAULT_MODEL = "qwen3.6:35b-a3b-coding-nvfp4"
DEFAULT_ENDPOINT = "http://localhost:11434"

# Queue mutex — serialises Queue A (contributor) vs Queue B (DRIFTJudge).
# Spec §4 / §7.7 — same model, different personas, never concurrent.
_QWEN_MUTEX = asyncio.Lock()


class QwenAdapter(ContributingAdapter):
    name = "qwen"

    def __init__(self, model: str = DEFAULT_MODEL, endpoint: str = DEFAULT_ENDPOINT,
                 queue: str = "A") -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.queue = queue  # "A" = contributor, "B" = DRIFTJudge

    async def auth_check(self) -> bool:
        # Ollama is local; "auth" = endpoint reachable.
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.endpoint}/api/tags")
                return r.status_code == 200
        except Exception:  # noqa: BLE001
            return False

    async def ask(self, prompt: str, *, timeout: float = 120.0) -> MemberResult | DroppedResult:
        async with _QWEN_MUTEX:
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    r = await client.post(
                        f"{self.endpoint}/api/chat",
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                        },
                    )
            except httpx.TimeoutException:
                return DroppedResult(member=self.name, reason="timeout",
                                     detail=f"after {timeout:.0f}s on queue {self.queue}")
            except httpx.HTTPError as e:
                return DroppedResult(member=self.name, reason="http_error", detail=str(e)[:200])
            elapsed = time.monotonic() - t0
            if r.status_code != 200:
                return DroppedResult(member=self.name, reason="http_status",
                                     detail=f"status={r.status_code} body={r.text[:200]}")
            try:
                obj = r.json()
                text = obj.get("message", {}).get("content", "") or ""
                model_used = obj.get("model")
            except Exception:  # noqa: BLE001
                text = r.text
                model_used = None
            return MemberResult(
                member=self.name, text=text.strip(),
                verdict=extract_verdict(text),
                model_used=model_used or self.model,
                duration_s=elapsed,
            )
