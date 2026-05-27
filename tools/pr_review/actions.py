"""Action handlers for the reviewer cron.

Each function wraps `gh` / `git` CLI calls and returns a success boolean so
the cron's dispatcher can fall through gracefully on failure (e.g. patch
doesn't apply → comment-only rather than partial commit).
"""
from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import tempfile

log = logging.getLogger(__name__)

REPO = os.environ.get("GH_REPO", "Silberud/typed-llm-council")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Run a subprocess; capture output; raise on non-zero by default."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("check", True)
    return subprocess.run(cmd, **kwargs)  # noqa: S603


def merge_pr(pr_number: int) -> bool:
    """Squash-merge a PR per CONTRIBUTING.md convention. Returns True on success."""
    try:
        _run(["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"])
        log.info("merged PR #%d", pr_number)
        return True
    except subprocess.CalledProcessError as e:
        log.warning("merge failed for PR #%d: %s", pr_number, e.stderr)
        return False


def pr_checks_green(pr_number: int) -> bool:
    """Return True only when GitHub reports non-empty, completed PR checks.

    The reviewer cron may act on LLM review verdicts, but merge is a higher-trust
    operation than commenting. Fail closed if checks are absent, pending,
    failing, or the GitHub API/CLI call itself fails.
    """
    import json

    try:
        res = _run(
            [
                "gh",
                "pr",
                "checks",
                str(pr_number),
                "--json",
                "name,state,bucket",
            ]
        )
    except subprocess.CalledProcessError as e:
        log.warning("check lookup failed for PR #%d: %s", pr_number, e.stderr)
        return False

    try:
        checks = json.loads(res.stdout)
    except json.JSONDecodeError:
        log.warning("check lookup returned invalid JSON for PR #%d", pr_number)
        return False

    if not checks:
        log.warning("PR #%d has no reported checks; refusing auto-merge", pr_number)
        return False

    green_states = {"pass", "success", "skipping", "skipped"}
    not_green = [
        c for c in checks
        if (c.get("bucket") or c.get("state") or "").lower() not in green_states
    ]
    if not_green:
        log.info("PR #%d checks are not green: %s", pr_number, not_green)
        return False
    return True


def push_fixup(pr_number: int, head_ref: str, patch_text: str, message: str) -> bool:
    """Apply a unified-diff patch to the PR branch and push it.

    Returns True on success, False on any failure (patch malformed, apply
    rejected, push blocked, …). On failure, the working tree is reset so the
    cron can fall through to comment-only without leaving partial state.
    """
    if not patch_text.strip():
        return False

    # Save patch to a temp file (git apply prefers file input over stdin for
    # error reporting).
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False) as f:
        f.write(patch_text)
        patch_path = pathlib.Path(f.name)

    try:
        # Make sure we're on the PR head ref locally
        _run(["git", "fetch", "origin", head_ref])
        _run(["git", "checkout", head_ref])

        # Apply the patch — --check first as a dry run
        try:
            _run(["git", "apply", "--check", str(patch_path)])
        except subprocess.CalledProcessError as e:
            log.warning("patch --check failed for PR #%d: %s", pr_number, e.stderr)
            return False

        _run(["git", "apply", str(patch_path)])

        # Commit + push
        _run(["git", "config", "user.name", "github-actions[bot]"])
        _run(
            [
                "git",
                "config",
                "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ]
        )

        # Stage everything modified by the patch
        _run(["git", "add", "-A"])

        # If nothing staged, skip
        diff_check = subprocess.run(
            ["git", "diff", "--staged", "--quiet"],
            check=False,
        )
        if diff_check.returncode == 0:
            log.info("patch produced no staged changes for PR #%d", pr_number)
            return False

        _run(["git", "commit", "-m", f"{message} [skip ci]"])
        _run(["git", "push", "origin", f"HEAD:{head_ref}"])
        log.info("pushed fixup to PR #%d (%s)", pr_number, head_ref)
        return True

    except subprocess.CalledProcessError as e:
        log.warning("push_fixup failed for PR #%d: %s", pr_number, e.stderr)
        # Reset to avoid leaving partial state
        try:
            _run(["git", "reset", "--hard"])
        except subprocess.CalledProcessError:
            pass
        return False
    finally:
        patch_path.unlink(missing_ok=True)


def comment_and_label(
    pr_number: int,
    body: str,
    label: str | None = None,
) -> None:
    """Post a PR comment and optionally apply a label. Never raises."""
    try:
        _run(["gh", "pr", "comment", str(pr_number), "--body", body])
        log.info("commented on PR #%d", pr_number)
    except subprocess.CalledProcessError as e:
        log.warning("comment failed for PR #%d: %s", pr_number, e.stderr)

    if label:
        try:
            _run(["gh", "pr", "edit", str(pr_number), "--add-label", label])
            log.info("labelled PR #%d with %r", pr_number, label)
        except subprocess.CalledProcessError as e:
            log.warning("label failed for PR #%d: %s", pr_number, e.stderr)


def list_open_prs() -> list[dict]:
    """Return the list of open PRs as parsed JSON dicts."""
    import json

    res = _run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,headRefName,headRefOid,author",
            "--limit",
            "100",
        ]
    )
    return json.loads(res.stdout)


def find_latest_review(pr_number: int, reviews_dir: pathlib.Path) -> pathlib.Path | None:
    """Return the latest docs/reviews/<n>-iter<k>.md for this PR, or None."""
    import re

    if not reviews_dir.exists():
        return None
    pattern = re.compile(rf"^{pr_number}-iter(\d+)\.md$")
    matches = [
        (int(m.group(1)), f) for f in reviews_dir.iterdir() if (m := pattern.match(f.name))
    ]
    if not matches:
        return None
    matches.sort()
    return matches[-1][1]
