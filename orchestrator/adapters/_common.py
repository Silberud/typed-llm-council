"""Shared helpers for adapters — subprocess invocation, verdict parsing."""
from __future__ import annotations
import asyncio
import re
import time
from typing import Sequence
from orchestrator.schemas.stage_output import DroppedResult, Verdict

_VERDICT_RE = re.compile(r"\b(APPROVE|REJECT|MODIFY)\b")


def extract_verdict(text: str | None) -> Verdict | None:
    """Pull the last APPROVE/REJECT/MODIFY token (the verdict line is at the end
    of the persona's output schema)."""
    if not text:
        return None
    matches = _VERDICT_RE.findall(text)
    return matches[-1] if matches else None  # type: ignore[return-value]


async def run_cli(
    argv: Sequence[str],
    *,
    stdin: str | None = None,
    timeout: float,
    member: str,
) -> tuple[int, str, str, float] | DroppedResult:
    """Run a CLI as subprocess; return (rc, stdout, stderr, elapsed) or DroppedResult.

    Never raises on subprocess failure — returns DroppedResult so the supervisor
    can count voters and apply spec §6 Stage 2 "continue iff ≥3 voters return"."""
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        return DroppedResult(member=member, reason="cli_missing", detail=str(e))
    except OSError as e:
        return DroppedResult(member=member, reason="exec_failed", detail=str(e))

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=stdin.encode() if stdin is not None else None),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass
        return DroppedResult(member=member, reason="timeout", detail=f"after {timeout:.0f}s")

    elapsed = time.monotonic() - t0
    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace"), elapsed
