"""PR review bot (v0).

Usage:
    python -m tools.pr_review --pr N [--dry-run]

Behaviour:
    1. Fetches PR metadata + diff via `gh api` (subprocess).
    2. Truncates diff to 50K chars if needed.
    3. Runs PI tripwire regex scan.
    4. Calls Claude (Opus 4.7) with a hardened system prompt.
    5. Writes docs/reviews/<PR>-iter<K>.md (K = 1 + existing review count for this PR).
    6. Prints the artefact path on stdout.

Environment:
    ANTHROPIC_API_KEY     required unless --dry-run
    PR_REVIEW_MODEL       optional; defaults to claude-opus-4-7
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
    if not REVIEWS_DIR.exists():
        return 1
    pattern = re.compile(rf"^{pr_number}-iter(\d+)\.md$")
    existing = [
        int(m.group(1))
        for f in REVIEWS_DIR.iterdir()
        if (m := pattern.match(f.name))
    ]
    return (max(existing) + 1) if existing else 1


def call_claude(system_prompt: str, user_message: str, model: str) -> str:
    """Single non-streamed Anthropic Messages call. Returns the text response."""
    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        sys.stderr.write(
            "anthropic package not installed. `pip install anthropic`.\n"
        )
        sys.exit(2)

    client = anthropic.Anthropic()  # picks up ANTHROPIC_API_KEY from env
    response = client.messages.create(
        model=model,
        max_tokens=8000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    # Concatenate any text blocks in the response.
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="PR review bot (v0)")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the artefact path that would be written; do not call the API.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("PR_REVIEW_MODEL", DEFAULT_MODEL),
    )
    args = parser.parse_args()

    # Gracefully no-op if the API key is missing — keeps the workflow green
    # on first install (before the operator sets the secret) and on any
    # ad-hoc run where the key isn't in the environment.
    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.stderr.write(
            "ANTHROPIC_API_KEY not set — skipping review. "
            "Set the repo secret to enable the bot.\n"
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
