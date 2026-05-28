"""Supervisor — orchestrator entrypoint.

Phase A+B+E build. Stages 0/1/2/4/5/6 are not yet implemented (Phases D, F,
G of the v2.3 plan). Stage 3 (CoVe verification) IS implemented and is
exercised by `orchestrator/tests/test_cove_isolation.py`.

Console scripts (per pyproject.toml [project.scripts]):
  council         → main()
  council-eval    → eval_main()
  council-replay  → replay_main()
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

# Config sits next to this module by default, so `pip install -e .` from any
# working directory just works. Override with the LLM_COUNCIL_CONFIG env var
# (e.g. for per-machine tuning without editing the package).
_DEFAULT_CONFIG = Path(__file__).parent / "config.toml"
CONFIG_PATH = Path(os.environ.get("LLM_COUNCIL_CONFIG", str(_DEFAULT_CONFIG)))

log = logging.getLogger("llm-council.supervisor")


# Update the `_show_status` note to point at the public-doc location.


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load config.toml with graceful fallback.

    On any read or parse error, return an empty dict so adapters fall back
    to their hardcoded module-level defaults. The error is logged but never
    raised — `council --status` must remain runnable even with a broken
    config so the operator can diagnose.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        log.warning("config.toml not found at %s — using adapter defaults", path)
        return {}
    except (tomllib.TOMLDecodeError, OSError) as e:
        log.warning("config.toml load failed (%s) — using adapter defaults", e)
        return {}


def build_adapters(config: dict[str, Any]) -> dict[str, Any]:
    """Instantiate all 6 adapters with config-derived parameters.

    Config keys honoured (all optional — missing keys fall back to adapter defaults):
      adapters.claude.{model, max_budget_usd}
      adapters.gemini.{model}
      adapters.gpt.{model, reasoning_effort}
      adapters.qwen.{model, endpoint}
      adapters.kimi.{model, endpoint}
    """
    from orchestrator.adapters.claude import ClaudeAdapter
    from orchestrator.adapters.gemini import GeminiAdapter
    from orchestrator.adapters.gpt import GPTAdapter
    from orchestrator.adapters.qwen import QwenAdapter
    from orchestrator.adapters.grok import GrokAdapter
    from orchestrator.adapters.kimi import KimiAdapter

    a = config.get("adapters", {}) if isinstance(config.get("adapters"), dict) else {}

    def cfg(name: str) -> dict[str, Any]:
        v = a.get(name, {})
        return v if isinstance(v, dict) else {}

    c, g, p, q, k = cfg("claude"), cfg("gemini"), cfg("gpt"), cfg("qwen"), cfg("kimi")

    return {
        "claude":   ClaudeAdapter(**{kk: c[kk] for kk in ("model", "max_budget_usd") if kk in c}),
        "gemini":   GeminiAdapter(**({"model": g["model"]} if "model" in g else {})),
        "gpt":      GPTAdapter(**{kk: p[kk] for kk in ("model", "reasoning_effort") if kk in p}),
        "qwen":     QwenAdapter(**{kk: q[kk] for kk in ("model", "endpoint") if kk in q}, queue="A"),
        "grok":     GrokAdapter(),
        # Wire the keychain_service/keychain_account fields from config through
        # to KimiAdapter so config.toml edits actually take effect (previously
        # silently ignored — Hermes review finding).
        "kimi":     KimiAdapter(**{kk: k[kk] for kk in
                                   ("model", "endpoint", "keychain_service", "keychain_account")
                                   if kk in k}),
    }


# ---------- status ----------
LABEL = {
    "claude": "claude  (Drafter/Chair)",
    "gemini": "gemini  (Researcher)",
    "gpt":    "gpt     (Architect)",
    "qwen":   "qwen    (Analyst Q-A)",
    "grok":   "grok    (Skeptic)",
    "kimi":   "kimi    (Verifier K2.6)",
}
ORDER = ["claude", "gemini", "gpt", "qwen", "grok", "kimi"]


async def _show_status(adapters: dict[str, Any]) -> bool:
    """Auth-only status (no live calls). Returns True if all expected seats authenticate."""
    print("H5R Council v2.3 — adapter auth status\n")
    all_ok = True
    for name in ORDER:
        a = adapters[name]
        ok = await a.auth_check()
        if name == "grok":
            mark = "·"
            note = " (stubbed; no OAuth path on X Premium+ — see docs/operator_setup.md → CG-001)"
        else:
            mark = "✓" if ok else "✗"
            note = ""
            if not ok:
                all_ok = False
        print(f"  {mark}  {LABEL[name]:<28}  auth={ok}{note}")
    return all_ok


async def _live_smoke(adapters: dict[str, Any]) -> bool:
    """Live trivial call to each contributing adapter + Kimi verifier ping.

    Burns a tiny amount of quota per adapter. Returns True iff all live calls
    succeed (Grok always counts as expected-DROPPED). Used for Phase β
    acceptance: prove the adapter actually talks to its model, not just that
    it instantiates.
    """
    from orchestrator.schemas.verifier_input import VerifierInput

    print("\nH5R Council v2.3 — LIVE smoke (one trivial call per seat)\n")
    all_ok = True
    for name in ORDER:
        a = adapters[name]
        if name == "grok":
            print(f"  ·  {LABEL[name]:<28}  skipped (stub adapter)")
            continue
        if name == "kimi":
            try:
                ans = await a.ask_verifier(VerifierInput(
                    operator_prompt="ping",
                    verification_question="Reply briefly. End with: CONFIDENCE: 0.99",
                ))
                ok = bool(ans.answer) and len(ans.answer) > 0
                preview = ans.answer[:80].replace("\n", " ⏎ ")
                print(f"  {'✓' if ok else '✗'}  {LABEL[name]:<28}  conf={ans.confidence:.2f}  → {preview!r}")
                if not ok:
                    all_ok = False
            except Exception as e:  # noqa: BLE001
                print(f"  ✗  {LABEL[name]:<28}  EXCEPTION: {type(e).__name__}: {e}")
                all_ok = False
            continue
        # Contributing adapters. 180s timeout gives gemini-cli's exponential
        # backoff (~10/20/40/80s on rate-limit) room to recover.
        try:
            res = await a.ask(f"Reply with exactly: {name} is reachable", timeout=180.0)
            from orchestrator.schemas.stage_output import DroppedResult
            if isinstance(res, DroppedResult):
                print(f"  ✗  {LABEL[name]:<28}  DROPPED: {res.reason} — {res.detail or ''}"[:120])
                all_ok = False
            else:
                ok = bool(res.text) and len(res.text) > 0
                preview = res.text[:80].replace("\n", " ⏎ ")
                print(f"  {'✓' if ok else '✗'}  {LABEL[name]:<28}  model={res.model_used or '?'}  → {preview!r}")
                if not ok:
                    all_ok = False
        except Exception as e:  # noqa: BLE001
            print(f"  ✗  {LABEL[name]:<28}  EXCEPTION: {type(e).__name__}: {e}")
            all_ok = False
    return all_ok


# ---------- CLI entrypoints ----------
def _load_convergence_ledger(path: Path):
    """Load and validate a ConvergenceLedger from JSON."""
    from pydantic import ValidationError

    from orchestrator.schemas.convergence import ConvergenceLedger

    try:
        return ConvergenceLedger.model_validate_json(path.read_text(encoding="utf-8")), None
    except (OSError, ValidationError, ValueError) as e:
        return None, e


def _convergence_summary(ledger: Any) -> dict[str, Any]:
    return {
        "valid": True,
        "run_id": ledger.run_id,
        "phase": ledger.phase.value,
        "status": ledger.status.value,
        "rounds": len(ledger.rounds),
        "consecutive_clean_rounds": ledger.consecutive_clean_rounds,
    }


def _handle_converge_command(args: argparse.Namespace) -> int:
    """Validate or replay a convergence ledger without live provider calls."""
    ledger, error = _load_convergence_ledger(args.ledger)
    if error is not None:
        print(json.dumps({"valid": False, "error": str(error)}, indent=2))
        return 1

    if args.converge_command == "validate":
        print(json.dumps(_convergence_summary(ledger), indent=2))
        return 0

    for round_ in ledger.rounds:
        print(
            f"round={round_.round_number} "
            f"artifact_version={round_.artifact_version} "
            f"verdict={round_.judge.verdict.value} "
            f"clean={round_.judge.clean_round}"
        )
    print(
        f"final status={ledger.status.value} "
        f"consecutive_clean_rounds={ledger.consecutive_clean_rounds}"
    )
    return 0


def _parse_converge_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="council converge", description="Inspect deterministic convergence ledgers.")
    subparsers = parser.add_subparsers(dest="converge_command", required=True)
    for name in ("validate", "replay"):
        command = subparsers.add_parser(name, help=f"{name.title()} a convergence ledger JSON file.")
        command.add_argument("ledger", type=Path, help="Path to a convergence ledger JSON file.")
    return parser.parse_args(argv)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) > 1 and sys.argv[1] == "converge":
        sys.exit(_handle_converge_command(_parse_converge_args(sys.argv[2:])))

    parser = argparse.ArgumentParser(
        prog="council",
        description="H5R LLM Council v2.3",
        epilog="Convergence ledger tools: council converge validate <ledger.json>; council converge replay <ledger.json>",
    )
    parser.add_argument("--status", action="store_true",
                        help="Show adapter auth status (no live calls).")
    parser.add_argument("--live", action="store_true",
                        help="With --status, additionally run a live trivial call against each seat.")
    parser.add_argument("prompt", nargs="?",
                        help="Operator prompt (Stages 0–6 not yet wired in this build).")
    args = parser.parse_args()

    config = load_config()
    adapters = build_adapters(config)

    if args.status:
        all_ok = asyncio.run(_show_status(adapters))
        if args.live:
            live_ok = asyncio.run(_live_smoke(adapters))
            sys.exit(0 if (all_ok and live_ok) else 1)
        sys.exit(0 if all_ok else 1)

    if args.prompt:
        print("Stages 0, 1, 2, 4, 5, 6 are not yet implemented in this build "
              "(Phases D/F/G of the v2.3 plan). Stage 3 (CoVe verifier) IS "
              "implemented; exercise it via the test suite:\n"
              "  pytest orchestrator/tests/test_cove_isolation.py -v",
              file=sys.stderr)
        sys.exit(2)

    parser.print_help()


def eval_main() -> None:
    print("council-eval is not yet implemented in this build (Phase H).", file=sys.stderr)
    sys.exit(2)


def replay_main() -> None:
    print("council-replay is not yet implemented in this build (Phase I).", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
