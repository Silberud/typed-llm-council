# Operator setup

Auth requirements per seat and the documented trade-offs that the H5R
operator hit during the v2.3 build. Most are not specific to H5R — they're
the live state of each provider's CLI / subscription as of 24 May 2026.

## What each seat needs

| Seat | Provider | Auth | Local hardware | Cost class |
|---|---|---|---|---|
| Claude (Drafter / Chair) | Anthropic | Claude Code CLI session (login) | — | $20–$200/mo plan |
| Gemini (Researcher) | Google | `gemini-cli` OAuth | — | Free tier (rate-limited) or AI Pro $20/mo |
| GPT (Architect) | OpenAI | Codex CLI + ChatGPT Pro OAuth | — | Pro $100–$200/mo |
| Qwen (Analyst) | Alibaba | none — local Ollama | ~30 GB VRAM for `qwen3.6:35b-a3b-coding-nvfp4` (works on M3 Max 64 GB) | one-time hardware |
| Grok (Skeptic) | xAI | **none — stubbed** (see below) | — | — |
| Kimi K2.6 (Verifier) | Moonshot | Moonshot API key (see EX-001) | — | pay-per-token, or $19/mo Kimi Code subscription |

## Documented exceptions and capability gaps

### EX-001 — Verifier seat uses API-key auth (spec invariant #4 exception)

The spec calls for subscription-OAuth on every seat. The H5R operator
elected to use a Moonshot API key for the Verifier seat instead of the
$19/mo Kimi Code OAuth subscription. The exception is bounded by spec
invariants #2 and #7 — the Verifier is non-voting and never sees any
council content other than the operator's original prompt + a single
factored verification question.

**To set up the key (operator equivalent):**

```bash
security add-generic-password \
  -a "moonshot-api-key" \
  -s "h5r-council-kimi-verifier" \
  -U -w "<YOUR_MOONSHOT_KEY>"
```

The Keychain service and account names are env-var overridable so you can
use your own scheme without editing the code:

```bash
export LLM_COUNCIL_KIMI_SERVICE="my-council-kimi"
export LLM_COUNCIL_KIMI_ACCOUNT="moonshot"
```

To rotate the key, use the same `add-generic-password -U` command with the
new key. The adapter reads it fresh from Keychain on every verifier call,
so rotation is picked up without restarting the orchestrator.

**Never write the key into any file in the repo** — `.gitignore` blocks
common secret-filename patterns as defence-in-depth, but the design relies
on the key only ever existing in Keychain.

### CG-001 — Skeptic seat (Grok) is stubbed

No subscription-OAuth Grok CLI works for the X Premium+ tier today. Grok
Build (xAI's official subscription-OAuth CLI) is allowlisted to SuperGrok
Heavy in its early-beta phase. Hermes Agent's `xai-oauth` provider names
X Premium+ in its model picker but xAI's backend has been observed to
reject standard subscribers. Invariant #4 forbids API keys.

**Consequence in this release:**
- `GrokAdapter` always returns `DroppedResult(reason="no_oauth_path_for_x_premium_plus")`.
- Stage 2 D3 critique runs with 3 jurors (Gemini, GPT, Qwen) plus the Advocate (Claude).
- Stage 4 AceMAD outcome-space is **9** (3 other voters × 3 verdicts), not 12.
  The peer-prediction module must be parameterised accordingly when Phase F lands.
- Stage 5 PoLL chair-rotation pool stays {Claude, Gemini, GPT}.

**Re-evaluate when** xAI opens OAuth on X Premium+ (or higher tiers
broaden Grok Build's beta).

### CG-002 — GPT/Codex model-pin assertion is degraded on Codex CLI 0.132.0

Spec §9.2 calls the model-pin assertion non-negotiable. Empirically,
Codex CLI 0.132.0 does not emit a `model` field in any of its `--json`
stage events (`task_started`, `agent_message`, `session_configured`). The
call still succeeds; the adapter logs a loud WARNING and defaults
`model_used` to the requested model, so the downstream `MemberResult` has
a value.

A silent provider-side downgrade would not be caught by the assertion
alone — it would only be visible through unexpectedly-changed output
style. Monitor the warning rate via telemetry once Phase H lands.

### TRANS-001 — Gemini OAuth capacity-throttled (transient observation)

During the v2.3 live smoke (24 May 2026), both `gemini-3.1-pro-preview`
and `gemini-2.5-pro` returned *"You have exhausted your capacity on this
model"* for the H5R operator's OAuth account. Gemini CLI handles it with
exponential backoff (~10 / 20 / 40 / 80 s); long-running smoke timeouts
(180s+) are required during heavy-throttle windows. Not a code bug —
quota resets per Google's window. Not specific to this operator either:
free-tier Gemini quotas tighten over time as usage scales.

## Env vars summary

| Var | Default | Purpose |
|---|---|---|
| `LLM_COUNCIL_CONFIG` | `<package>/config.toml` | override config file path |
| `LLM_COUNCIL_KIMI_SERVICE` | `h5r-council-kimi-verifier` | Keychain service name for Kimi |
| `LLM_COUNCIL_KIMI_ACCOUNT` | `moonshot-api-key` | Keychain account name for Kimi |
