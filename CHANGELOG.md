# Changelog

## v2.3.0 — initial release (private staging)

Phase A + Phase B + Phase E.0 + Phase E.1 of the 9-phase council plan.

### Added
- Orchestrator skeleton + supervisor entrypoint with graceful-fallback config loader.
- Six adapter interfaces: Claude / Gemini / GPT / Qwen contributing; Grok stub; Kimi verifier.
- Pydantic schemas: `VerifierInput` (frozen, `extra="forbid"`), `MemberResult`, `DroppedResult`, `VerifierAnswer`, `Vote`.
- Adapter base-class split (`ContributingAdapter` / `VerifierAdapter`) that gives `KimiAdapter` no `ask()` method.
- Stage 3 CoVe verifier with three-layer isolation (schema + adapter + content).
- `services/leak_filter.py` — n-gram window + role-marker leak detection (Phase E.1, 2026-05-25 hardening pass).
- `tests/test_cove_isolation.py` — 16 cases incl. 50-fixture Hypothesis fuzz on layers 1+2.
- `tests/test_leak_filter.py` — 12 cases incl. regression test patching a leaky decomposer.
- `tests/test_adapter_smoke.py` — 11 structural Phase B smoke tests.
- Runtime `isinstance(input, VerifierInput)` check in `KimiAdapter.ask_verifier` (belt-and-suspenders against duck-typed inputs).
- Kimi endpoint allowlist (HTTPS-only, `api.moonshot.{ai,cn}` only unless `LLM_COUNCIL_KIMI_ENDPOINT_UNSAFE=1`).
- Env-var-overridable Keychain service/account for Kimi (`LLM_COUNCIL_KIMI_SERVICE`, `LLM_COUNCIL_KIMI_ACCOUNT`).
- `confidence_parsed: bool` field on `VerifierAnswer` so Phase E.2's real comparator can route unparsed answers to "needs review."
- GitHub Actions CI: ruff (blocking) + pytest on Python 3.11 and 3.12.

### Documented
- `README.md` — design hypothesis, status table (Phase E split into E.0/E.1/E.2), 5 feedback questions, non-affiliation disclaimer, no-telemetry-collection note.
- `docs/internal_spec_v2.2.md` — historical implementation directive (provenance preserved; clearly labelled as internal).
- `docs/design_notes.md` — citation status, structural-vs-prompt isolation rationale, force-verdicts rationale, quarantined-Chairman rationale.
- `docs/operator_setup.md` — auth requirements per seat + EX-001 (Kimi API key) + CG-001 (Grok stub) + CG-002 (Codex model-pin degraded) + TRANS-001 (Gemini quota throttle).
- `CONTRIBUTING.md` — pointers to load-bearing files; `_live/` test warning.

### Known limitations (carried into this release)
- **Phase E.2 (real CoVe comparator):** `compare_answers_placeholder` is a confidence-threshold heuristic, **not** a real factual-alignment comparator. Phase E.2 will replace it.
- **Phase D (Stages 0/1/2/5):** not implemented — `council <prompt>` exits non-zero.
- **Phase C/F/G/H:** not implemented — see status table.
- **Grok seat:** stubbed (no subscription-OAuth path on X Premium+).
- **GPT model-pin:** Codex CLI 0.132.0 doesn't emit model id in events; the assertion logs a warning instead of asserting (CG-002).
- **argv prompt visibility:** Gemini and GPT adapters pass the prompt as positional argv. Hermes-review finding; deferred to a future hardening pass to avoid breaking the working live integration smoke. Claude adapter already uses stdin.
