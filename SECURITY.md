# Security Policy

## Scope

This policy applies to source code in this repository.

**Out of scope:** vulnerabilities in any third-party model provider whose CLI or API this project invokes (Anthropic, Google, OpenAI, Alibaba/Qwen, xAI, Moonshot). Please report those directly to the relevant provider's security team.

## Reporting a vulnerability

Email **igor.silberud@gmail.com** with the subject line `[typed-llm-council] security`.

Please include:
- A short description of the issue
- A reproducer (or pointer to relevant code paths)
- Your assessment of impact
- Whether you intend to disclose publicly, and any preferred timeline

**Do not** open a public Issue or Discussion for vulnerabilities that could be exploited before a fix lands.

## Response

This is a personal project; responses are best-effort. You should expect:
- An acknowledgement within **7 days** that your report was received.
- A determination within **14 days** of whether the report is in scope and the severity assessment.
- A fix or mitigation timeline communicated within **30 days** for accepted reports.

There is **no bounty**. Credit (with your consent) in the release notes or in a thank-you Discussion comment is the only form of recognition.

## Secret-handling expectations for contributors

Several seats in this council use API keys or OAuth credentials:

- **Kimi (Verifier) API key** → macOS Keychain (`security add-generic-password`); never on disk.
- **Anthropic / OpenAI / Google / xAI credentials** → handled by their respective CLIs (`claude`, `codex`, `gemini`, etc.), not by this project.
- **Ollama (Qwen)** → no credentials; local-only HTTP.

**If you submit a PR that introduces a new secret-handling code path, the PR must:**
1. Document where the secret lives (Keychain entry, environment variable, etc.)
2. Confirm `.gitignore` blocks any plausible accidental commit (`.env`, `*.key`, `secrets.*`, etc.)
3. Never include the secret itself in code, tests, or commit messages.

## Known operational caveats (not security issues, but worth knowing)

- The Stage 3 leak filter (`services/leak_filter.py`) is a heuristic content-channel guard, not a formal noninterference proof. Paraphrastic leakage can still pass; see `docs/design_notes.md`.
- Endpoint allowlist for the Kimi adapter is enforced (HTTPS only, `api.moonshot.{ai,cn}`). Override via `LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1` is an explicit opt-in.

## No telemetry

This code does not send any telemetry, error reports, or usage data to the maintainer or to any third party. Everything happens locally on your machine, except for the model API calls you explicitly authorise via your own credentials.
