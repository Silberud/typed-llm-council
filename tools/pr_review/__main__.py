"""PR review bot (v0).

Usage:
    python -m tools.pr_review --pr N [--dry-run]

Behaviour:
    1. Fetches PR metadata + diff via `gh api` (subprocess).
    2. Truncates diff to 50K chars if needed.
    3. Runs PI tripwire regex scan.
    4. Calls Claude via the `claude` CLI (subscription-auth, OAuth token).
    5. Writes docs/reviews/<PR>-iter<K>.md (K = 1 + existing review count for this PR).
    6. Prints the artefact path on stdout.

Environment:
    CLAUDE_CODE_OAUTH_TOKEN     required unless --dry-run; subscription auth.
                                Populated in CI by `claude` + `/install-github-app`.
    PR_REVIEW_MODEL             optional; passed to `claude --model`.
    PR_REVIEW_EXISTING_REVIEWS_DIR
                                optional; directory used only to count prior
                                docs/reviews/<PR>-iter<K>.md artefacts
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

from .prompts import SYSTEM_PROMPT, build_user_message, scan_for_injection

REPO = "Silberud/typed-llm-council"
DIFF_TRUNCATE_AT = 50_000
DEFAULT_MODEL = "claude-opus-4-7"
REVIEWS_DIR = pathlib.Path("docs/reviews")


def _gh(*args: str) -> str:
    """Run a `gh` subcommand and return stdout. Errors raise."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def fetch_pr(pr_number: int) -> tuple[dict, str, bool]:
    """Fetch PR metadata + diff. Returns (metadata, diff_text, was_truncated)."""
    metadata = json.loads(_gh("api", f"repos/{REPO}/pulls/{pr_number}"))
    diff = _gh(
        "api",
        f"repos/{REPO}/pulls/{pr_number}",
        "-H", "Accept: application/vnd.github.diff",
    )
    truncated = False
    if len(diff) > DIFF_TRUNCATE_AT:
        diff = diff[:DIFF_TRUNCATE_AT]
        truncated = True
    return metadata, diff, truncated


def next_iteration(pr_number: int) -> int:
    """K = 1 + count of existing reviews for this PR."""
    reviews_dir = pathlib.Path(
        os.environ.get("PR_REVIEW_EXISTING_REVIEWS_DIR", str(REVIEWS_DIR))
    )
    if not reviews_dir.exists():
        return 1
    pattern = re.compile(rf"^{pr_number}-iter(\d+)\.md$")
    existing = [
        int(m.group(1))
        for f in reviews_dir.iterdir()
        if (m := pattern.match(f.name))
    ]
    return (max(existing) + 1) if existing else 1


def call_claude(system_prompt: str, user_message: str, model: str) -> str:
    """Single headless invocation of the `claude` CLI.

    Auth: reads `CLAUDE_CODE_OAUTH_TOKEN` from environment (set by the workflow
    from the repo secret). This bills against the Claude Code Pro/Max
    subscription, not a separate API key.

    Returns the text response (stdout of `claude -p`).
    """
    cmd = ["claude", "-p", user_message, "--append-system-prompt", system_prompt]
    if model and model != "default":
        cmd.extend(["--model", model])
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.stderr.write(
            "claude CLI not installed. "
            "Install with `npm install -g @anthropic-ai/claude-code`.\n"
        )
        sys.exit(2)
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"claude CLI failed (exit {e.returncode}):\n{e.stderr}\n")
        sys.exit(2)
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="PR review bot (v0)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the artefact path that would be written; do not call the API.",
    )
    parser.add_argument(
        "--verdict-only",
        action="store_true",
        help="Don't call the API; instead read the latest existing review file for this PR and print just its verdict token on stdout.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("PR_REVIEW_MODEL", DEFAULT_MODEL),
    )
    args = parser.parse_args()

    if args.verdict_only:
        # Lazy import to avoid pulling actions.py into the hot path.
        from .actions import find_latest_review  # noqa: PLC0415
        from .cron import parse_verdict  # noqa: PLC0415

        path = find_latest_review(args.pr, REVIEWS_DIR)
        if not path:
            return 0  # no review yet; empty stdout signals caller
        verdict = parse_verdict(path)
        if verdict:
            print(verdict)
        return 0

    # Gracefully no-op if the OAuth token is missing — keeps the workflow
    # green on first install (before the operator runs `claude` then
    # `/install-github-app` which populates the secret) and on any ad-hoc run
    # where the token isn't in the environment.
    if not args.dry_run and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        sys.stderr.write(
            "CLAUDE_CODE_OAUTH_TOKEN not set — skipping review. "
            "Run `claude` then `/install-github-app` to populate the repo secret.\n"
        )
        return 0

    metadata, diff_text, was_truncated = fetch_pr(args.pr)
    pi_flags = scan_for_injection(
        " ".join(
            [
                metadata.get("title") or "",
                metadata.get("body") or "",
                diff_text,
            ]
        )
    )
    iteration = next_iteration(args.pr)
    output_path = REVIEWS_DIR / f"{args.pr}-iter{iteration}.md"

    if args.dry_run:
        print(f"[dry-run] would write: {output_path}")
        print(f"[dry-run] PI flags: {len(pi_flags)}")
        print(f"[dry-run] diff truncated: {was_truncated}")
        return 0

    user_msg = build_user_message(
        pr_number=args.pr,
        iteration=iteration,
        pr_metadata=metadata,
        diff_text=diff_text,
        diff_truncated=was_truncated,
        pi_flags=pi_flags,
    )

    review_md = call_claude(SYSTEM_PROMPT, user_msg, args.model)

    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review_md)
    print(str(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
