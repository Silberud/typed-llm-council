"""Reviewer cron: runs every 6h, iterates open PRs, acts on verdicts.

Decision table:
  APPROVE                     → merge_pr
  APPROVE-WITH-MINOR-MODIFY   → comment "soft notes; merging", merge_pr
  MODIFY                      → ask Claude for unified-diff patch; push_fixup
                                if it applies cleanly, else comment-only
  REJECT                      → comment + label "needs-maintainer"
  NEEDS-MAINTAINER            → comment + label "needs-maintainer"
  <empty> / parse error       → no-op, log warning

Each PR is wrapped in try/except so a single bad PR doesn't block the rest.

Usage:
    python -m tools.pr_review.cron [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import re
import subprocess
import sys

from .actions import (
    comment_and_label,
    find_latest_review,
    list_open_prs,
    merge_pr,
    pr_checks_green,
    push_fixup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("reviewer_cron")

REVIEWS_DIR = pathlib.Path("docs/reviews")
DEFAULT_MODEL = os.environ.get("PR_REVIEW_MODEL", "claude-opus-4-7")

VERDICT_PATTERN = re.compile(
    # Match the verdict token bolded; allow optional trailing punctuation/text
    # inside the bold span (e.g. "**APPROVE.**" or "**MODIFY — see below**").
    r"\*\*(APPROVE-WITH-MINOR-MODIFY|APPROVE|MODIFY|REJECT|NEEDS-MAINTAINER)\b[^*]*\*\*",
    re.IGNORECASE,
)

# Excerpt windows for the comment posted on REJECT / NEEDS-MAINTAINER.
COMMENT_HEADER = "🔎 Automated review (reviewer cron)"


def parse_verdict(review_path: pathlib.Path) -> str | None:
    """Extract the bold verdict token from the review's Decision section."""
    text = review_path.read_text(errors="replace")
    # Find the Decision section, then the first bold token within it.
    m = re.search(r"## Decision\b(.*?)(\n## |\Z)", text, re.S)
    if not m:
        return None
    decision_section = m.group(1)
    vm = VERDICT_PATTERN.search(decision_section)
    return vm.group(1).upper() if vm else None


def extract_required_actions(review_path: pathlib.Path) -> str:
    """Pull the 'Required actions before merge' subsection (or empty)."""
    text = review_path.read_text(errors="replace")
    m = re.search(
        r"### Required actions before merge\b(.*?)(\n### |\n## |\Z)",
        text,
        re.S,
    )
    return m.group(1).strip() if m else ""


def run_review_for_pr(pr_number: int) -> pathlib.Path | None:
    """Invoke the v0 reviewer for this PR; return the new artefact path or None."""
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        log.info("PR #%d: CLAUDE_CODE_OAUTH_TOKEN unset; skipping", pr_number)
        return None
    try:
        res = subprocess.run(
            [sys.executable, "-m", "tools.pr_review", "--pr", str(pr_number)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        log.warning("PR #%d: review subprocess failed: %s", pr_number, e.stderr)
        return None
    out = res.stdout.strip()
    if not out:
        log.info("PR #%d: review subprocess returned empty (no key?)", pr_number)
        return None
    return pathlib.Path(out)


def claude_generate_patch(review_path: pathlib.Path, pr_number: int) -> str:
    """Ask Claude (via the `claude` CLI) for a unified-diff patch addressing
    this review's required actions.

    Returns empty string if no token, no required actions, or generation fails.
    """
    required = extract_required_actions(review_path)
    if not required or required.lower() == "none":
        return ""
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return ""

    # Fetch the current PR diff so Claude has context for the patch.
    try:
        pr_diff = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{os.environ.get('GH_REPO', 'Silberud/typed-llm-council')}/pulls/{pr_number}",
                "-H",
                "Accept: application/vnd.github.diff",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return ""

    system = (
        "You generate unified-diff patches. Output ONLY a valid unified diff "
        "(no prose, no fences, no markdown). The diff must apply cleanly with "
        "`git apply` against the PR branch's current state. If you cannot "
        "address the required actions safely with a diff, output an empty string."
    )
    user = f"""\
PR #{pr_number} review identified these required actions:

<REQUIRED_ACTIONS>
{required}
</REQUIRED_ACTIONS>

Current PR diff (the changes this PR introduces — your patch will be applied ON TOP of these on the PR branch):

<UNTRUSTED_PR_DIFF>
{pr_diff[:30000]}
</UNTRUSTED_PR_DIFF>

Produce a minimal unified diff that addresses the Required Actions. Output the diff only, no surrounding text. If unsafe, output nothing.
"""

    try:
        result = subprocess.run(  # noqa: S603
            ["claude", "-p", "--append-system-prompt", system],
            input=user,
            capture_output=True,
            text=True,
            check=True,
        )
        patch = result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        log.warning("PR #%d: claude patch generation failed: %s", pr_number, e)
        return ""

    # Strip markdown fences if Claude added them despite instructions
    patch = re.sub(r"^```[a-z]*\n", "", patch.strip())
    patch = re.sub(r"\n```$", "", patch)
    return patch.strip()


def dispatch(pr: dict, verdict: str | None, review_path: pathlib.Path, dry_run: bool) -> str:
    """Take action based on verdict. Returns the action label for logging."""
    n = pr["number"]
    head_ref = pr["headRefName"]
    excerpt = review_path.read_text(errors="replace")[-1500:]  # tail of review

    if verdict in ("APPROVE", "APPROVE-WITH-MINOR-MODIFY"):
        if dry_run:
            return f"would-merge-if-checks-green ({verdict})"
        if not pr_checks_green(n):
            comment_and_label(
                n,
                f"{COMMENT_HEADER}: verdict {verdict}, but auto-merge is blocked "
                "because PR checks are absent, pending, or not green. Maintainer "
                f"review required. See [`{review_path}`].",
                label="needs-maintainer",
            )
            return "blocked-checks-not-green"
        if verdict == "APPROVE-WITH-MINOR-MODIFY":
            comment_and_label(
                n,
                f"{COMMENT_HEADER}: soft suggestions noted in [`{review_path}`]. Merging.",
            )
        ok = merge_pr(n)
        return "merged" if ok else "merge-failed"

    if verdict == "MODIFY":
        if dry_run:
            return "would-attempt-fixup"
        patch = claude_generate_patch(review_path, n)
        if patch:
            applied = push_fixup(
                n,
                head_ref,
                patch,
                message=f"fixup: address review {review_path.name}",
            )
            if applied:
                comment_and_label(
                    n,
                    f"{COMMENT_HEADER}: pushed auto-fixup addressing required actions. "
                    f"Per-PR bot will re-review on the new commit. See [`{review_path}`].",
                )
                return "fixup-pushed"
        # Fall through: comment-only
        comment_and_label(
            n,
            f"{COMMENT_HEADER}: verdict MODIFY — auto-fixup not attempted/possible. "
            f"Required actions are in [`{review_path}`].",
            label="needs-modify",
        )
        return "comment-only-modify"

    if verdict in ("REJECT", "NEEDS-MAINTAINER"):
        if dry_run:
            return f"would-comment+label ({verdict})"
        comment_and_label(
            n,
            f"{COMMENT_HEADER}: verdict {verdict}. See [`{review_path}`].\n\n"
            f"<details><summary>Review tail</summary>\n\n```\n{excerpt[-800:]}\n```\n</details>",
            label="needs-maintainer",
        )
        return f"escalated ({verdict})"

    log.warning("PR #%d: unknown / unparsed verdict %r — no action", n, verdict)
    return "no-action"


def process_pr(pr: dict, dry_run: bool) -> tuple[int, str | None, str]:
    """Run review-if-needed, parse verdict, dispatch. Returns (number, verdict, action)."""
    n = pr["number"]
    head_sha = pr["headRefOid"]

    review_path = find_latest_review(n, REVIEWS_DIR)
    needs_fresh_review = True

    if review_path:
        # If the existing review was written for the current HEAD SHA, reuse it.
        existing_text = review_path.read_text(errors="replace")
        if head_sha and head_sha[:7] in existing_text:
            needs_fresh_review = False
            log.info("PR #%d: existing review %s covers current HEAD", n, review_path.name)

    if needs_fresh_review and not dry_run:
        log.info("PR #%d: generating fresh review", n)
        review_path = run_review_for_pr(n) or review_path

    if review_path is None:
        return n, None, "no-review-available"

    verdict = parse_verdict(review_path)
    action = dispatch(pr, verdict, review_path, dry_run)
    return n, verdict, action


def main() -> int:
    parser = argparse.ArgumentParser(description="Reviewer cron")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List intended actions; do not call APIs or push.",
    )
    args = parser.parse_args()

    if not args.dry_run and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        log.warning("CLAUDE_CODE_OAUTH_TOKEN not set — running in degraded mode (no fresh reviews, no patches; can still parse existing reviews and act).")

    try:
        prs = list_open_prs()
    except subprocess.CalledProcessError as e:
        log.error("failed to list open PRs: %s", e.stderr)
        return 1

    log.info("processing %d open PR(s)", len(prs))
    results = []
    for pr in prs:
        try:
            n, verdict, action = process_pr(pr, args.dry_run)
            results.append((n, verdict, action))
            log.info("PR #%d: verdict=%s action=%s", n, verdict, action)
        except Exception as e:  # noqa: BLE001
            log.exception("PR #%d: unhandled error: %s", pr.get("number"), e)

    # Summary line at the end so the GH Actions log makes the result obvious.
    print(json.dumps({"results": [{"pr": n, "verdict": v, "action": a} for n, v, a in results]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
