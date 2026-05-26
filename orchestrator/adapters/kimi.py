"""Kimi K2.6 adapter — The Verifier seat (CoVe, Stage 3 ONLY, non-voting).

DESIGN INVARIANTS — non-negotiable:
  - This adapter inherits from VerifierAdapter, NOT ContributingAdapter.
    Consequence: it has NO `ask()` method. Attempting to call adapter.ask()
    raises AttributeError. tests/test_cove_isolation.py enforces this.
  - The ONLY method exposed is `ask_verifier(input: VerifierInput) -> VerifierAnswer`.
    `VerifierInput` is a frozen Pydantic model with `extra='forbid'` — any
    EXTRA structured field referring to Draft D, framing, persona, or
    council deliberation raises ValidationError at construction.

  IMPORTANT — what the schema layer does NOT cover:
    The schema constrains which FIELDS exist, not the CONTENT of the two
    allowed fields. A `VerifierInput.verification_question` could in
    principle carry draft content if it were constructed that way. The
    *content channel* is closed by `services/leak_filter.py`, which Stage 3
    applies between decomposition and this method. This adapter trusts
    that filter; it does not re-verify content.
  - Auth: spec §4 invariant requires subscription-OAuth. docs/operator_setup.md
    documents the EX-001 exception — the H5R operator chose Moonshot API-key
    auth (Keychain-sourced) instead of the $19/mo Kimi Code subscription.
    With the API-key route we hit the Moonshot HTTP API directly rather than
    the `kimi` CLI (which requires OAuth login).

KEYCHAIN_SERVICE / KEYCHAIN_ACCOUNT are env-var overridable so other
operators can use their own Keychain entries without editing this file.
"""
# NOTE: deliberately NOT using `from __future__ import annotations` here.
# Under PEP 563 the `input: VerifierInput` annotation on ask_verifier would
# become the string 'VerifierInput', and `inspect.signature(...).parameters[1]
# .annotation == VerifierInput` (asserted by test_cove_isolation.py) would
# fail. Eager evaluation keeps the type annotation as the actual class object.
import asyncio
import logging
import os
import subprocess
import time
from urllib.parse import urlparse
import httpx
from orchestrator.adapters.base import VerifierAdapter
from orchestrator.schemas.verifier_input import VerifierInput
from orchestrator.schemas.stage_output import VerifierAnswer

log = logging.getLogger("llm-council.adapters.kimi")

DEFAULT_MODEL = "kimi-k2.6"
DEFAULT_ENDPOINT = "https://api.moonshot.ai/v1/chat/completions"
KEYCHAIN_SERVICE = os.environ.get("LLM_COUNCIL_KIMI_SERVICE", "h5r-council-kimi-verifier")
KEYCHAIN_ACCOUNT = os.environ.get("LLM_COUNCIL_KIMI_ACCOUNT", "moonshot-api-key")

# Endpoint-host allowlist. Sending a Bearer token to an arbitrary URL would
# exfiltrate the API key, so the endpoint hostname must be on this list
# unless the operator explicitly sets LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1.
ALLOWED_ENDPOINT_HOSTS: frozenset[str] = frozenset({
    "api.moonshot.ai", "api.moonshot.cn",
})


def _validate_endpoint(url: str) -> None:
    """Raise ValueError if the endpoint URL would leak the Bearer token to a
    non-allowlisted host or to a non-HTTPS scheme.

    Override (operator-acknowledged unsafe):
        LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(
            f"Kimi endpoint must be HTTPS (got {parsed.scheme!r} for {url!r}); "
            f"a Bearer token must never transit cleartext."
        )
    if os.environ.get("LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE") == "1":
        log.warning(
            "LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1 — skipping endpoint allowlist "
            "check for %r. Sending Bearer token to this host is your call.",
            parsed.hostname,
        )
        return
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_ENDPOINT_HOSTS:
        raise ValueError(
            f"Kimi endpoint host {host!r} is not in the allowlist "
            f"{sorted(ALLOWED_ENDPOINT_HOSTS)!r}. Set "
            f"LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1 to override."
        )


def _read_keychain_key(service: str = KEYCHAIN_SERVICE,
                        account: str = KEYCHAIN_ACCOUNT) -> str:
    """Read the Moonshot API key from macOS Keychain. Never cached on disk.

    Called fresh for each verifier invocation so a Keychain rotation is picked
    up without restarting the orchestrator."""
    out = subprocess.run(
        ["security", "find-generic-password",
         "-a", account, "-s", service, "-w"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"Moonshot API key not found in Keychain "
            f"(service={service!r}, account={account!r}). "
            f"See docs/operator_setup.md → Secret handling for the rotation procedure."
        )
    return out.stdout.strip()


class KimiAdapter(VerifierAdapter):
    """The Verifier — Kimi K2.6, non-voting. Type-restricted to VerifierInput.

    Note the absence of any `ask()` method. This is structural, not nominal:
    `hasattr(KimiAdapter(), 'ask')` is False, and inspect.signature will fail
    on it. CI test asserts both.
    """
    name = "kimi"

    def __init__(self, model: str = DEFAULT_MODEL, endpoint: str = DEFAULT_ENDPOINT,
                 keychain_service: str | None = None,
                 keychain_account: str | None = None) -> None:
        _validate_endpoint(endpoint)  # fail fast on bad endpoint
        self.model = model
        self.endpoint = endpoint
        # Allow per-instance override of keychain entries (e.g. for tests or
        # multi-tenant setups). Falls back to module-level defaults (which
        # are themselves env-var overridable).
        self.keychain_service = keychain_service or KEYCHAIN_SERVICE
        self.keychain_account = keychain_account or KEYCHAIN_ACCOUNT

    async def auth_check(self) -> bool:
        try:
            key = await asyncio.to_thread(
                _read_keychain_key, self.keychain_service, self.keychain_account,
            )
            return bool(key) and len(key) > 8
        except Exception:  # noqa: BLE001
            return False

    async def ask_verifier(self, input: VerifierInput) -> VerifierAnswer:
        """The ONLY method on this adapter. Input is type-locked at the schema
        level — draft/framing/persona content cannot be smuggled in."""
        # Belt-and-suspenders runtime type check. The signature annotation is
        # informative under PEP 563-style lazy evaluation but doesn't enforce
        # at runtime — a duck-typed object with the right attributes would
        # otherwise sneak through. Raise loudly here.
        if not isinstance(input, VerifierInput):
            raise TypeError(
                f"KimiAdapter.ask_verifier requires a VerifierInput instance, "
                f"got {type(input).__name__}"
            )
        # Use per-instance keychain entries (which default to module-level
        # env-overridable constants).
        key = await asyncio.to_thread(
            _read_keychain_key, self.keychain_service, self.keychain_account,
        )
        t0 = time.monotonic()
        # Compose the user message from JUST the operator_prompt and the
        # single verification_question. Nothing else is in scope.
        user_content = (
            f"Operator's original question:\n{input.operator_prompt}\n\n"
            f"Verification question (answer concisely; provide your confidence 0.0–1.0):\n"
            f"{input.verification_question}"
        )
        # 120s per verifier call — K2.6 inference is large-model-slow and
        # Stage 3 fires up to 5 in parallel, increasing tail latency.
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": user_content}],
                    # NOTE: kimi-k2.6 enforces temperature=1 server-side; sending
                    # any other value yields 400 "invalid temperature". Omit the
                    # field entirely so the model uses its enforced default.
                },
            )
        elapsed = time.monotonic() - t0  # noqa: F841  (kept for future telemetry; Phase H)
        del elapsed
        if r.status_code >= 400:
            # Surface the structured error body so a future regression is debuggable
            # without re-running the whole council.
            raise RuntimeError(
                f"Moonshot {r.status_code}: {r.text[:400]}"
            )
        obj = r.json()
        text = ""
        try:
            text = obj["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            text = ""
        # Confidence heuristic: look for an explicit numeric in the response.
        # If unparseable, default to 0.5 (NOT 0.7) so the comparator routes
        # the response to "needs review" rather than silently counting it
        # as agreement. Track parse status explicitly via VerifierAnswer
        # `confidence_parsed` so a future real comparator (Phase E.2) can
        # treat unparsed answers differently from genuinely low-confidence ones.
        import re
        m = re.search(r"confidence[^0-9]{0,10}([01](?:\.\d+)?)", text, re.IGNORECASE)
        conf_parsed = m is not None
        conf = float(m.group(1)) if conf_parsed else 0.5
        conf = max(0.0, min(1.0, conf))
        return VerifierAnswer(
            answer=text.strip(),
            confidence=conf,
            confidence_parsed=conf_parsed,
            model_used=obj.get("model"),
        )
