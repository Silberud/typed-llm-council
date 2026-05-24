"""Grok adapter — The Skeptic seat. STUBBED.

Decision recorded 2026-05-20: no subscription-OAuth Grok CLI works for the
X Premium+ tier today (Grok Build is allowlisted to SuperGrok Heavy), and
spec invariant #4 forbids API keys.

This adapter therefore always returns DroppedResult. The council runs with
4 contributing voters (Claude, Gemini, GPT, Qwen) until xAI opens an OAuth
path on X Premium+ — at which point this stub is replaced with a real
adapter and the AceMAD outcome-space size changes from 9 (3 other × 3
verdicts) back to 12 (4 × 3).

See docs/operator_setup.md → "Skeptic seat (Grok) is stubbed".
"""
from __future__ import annotations
from orchestrator.adapters.base import ContributingAdapter
from orchestrator.schemas.stage_output import DroppedResult, MemberResult


class GrokAdapter(ContributingAdapter):
    name = "grok"

    async def auth_check(self) -> bool:
        return False  # never authenticated until OAuth path exists

    async def ask(self, prompt: str, *, timeout: float = 90.0) -> MemberResult | DroppedResult:
        return DroppedResult(
            member=self.name,
            reason="no_oauth_path_for_x_premium_plus",
            detail=(
                "Grok Build (xAI's official subscription-OAuth CLI) is gated to "
                "SuperGrok Heavy; X Premium+ tier is not eligible. Invariant #4 "
                "forbids API-key auth. See docs/operator_setup.md."
            ),
        )
