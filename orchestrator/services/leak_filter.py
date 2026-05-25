"""Post-decomposition leak filter (Tier 1 hardening, 2026-05-25).

Closes the boundary that the Pydantic VerifierInput schema can't reach: the
*content* of `verification_question` and `operator_prompt` fields. Structural
isolation (frozen + extra='forbid' + VerifierAdapter-only) blocks extra
fields from crossing to Kimi, but a leaky decomposer could put draft sentences
or council-meta language INSIDE the allowed fields.

This filter sits between `decompose_draft()` and `kimi.ask_verifier()` in
Stage 3, and fails closed when:

1. Any n-gram window (default 8 words) from draft_text or framing_note
   appears verbatim in the question — unless that same window also appears
   in operator_prompt (legitimate operator-supplied context).
2. Any role/council-meta marker ("advocate", "juror", "skeptic", "chairman",
   "council", "consensus", "dissent", "draft says", etc.) appears in the
   question or operator_prompt — unless that marker also appears in the
   operator's original prompt (legitimate operator-supplied context).

Allowed by design: noun-phrase claim restatement (e.g., "Does Python 3.12
include PEP 695?") — that's how CoVe questions normally work. The 8-word
threshold tolerates short claim restatements while blocking longer verbatim
copies that would carry drafter reasoning into the verifier sandbox.

Tuneable via constants below; defaults chosen so the Python-3.12 live
integration smoke continues to pass while a deliberately-leaky decomposer
(see tests/test_leak_filter.py) is blocked.
"""
from __future__ import annotations
from typing import Iterable

# Default n-gram window. Below this, claim restatements like "Python 3.12
# includes PEP 695" are allowed through. Above this, the question carries
# enough drafter prose to be a real leak.
DEFAULT_WINDOW = 8

# Role/council-meta marker phrases. Lowercased, matched case-insensitively.
# Multi-word ONLY — single words like "council" or "consensus" are too
# generic to flag (Hypothesis fuzz found "COUNCIL000" triggering false
# positives during testing). Multi-word phrases are far less likely to
# appear in legitimate operator vocabulary and far more likely to indicate
# council-meta language being injected by a leaky decomposer or tampered
# upstream code.
ROLE_MARKERS: tuple[str, ...] = (
    "the advocate", "the juror", "the skeptic", "the chairman",
    "the drafter", "the analyst", "the researcher", "the architect",
    "advocate defence", "advocate argued", "advocate said",
    "juror critique", "juror argued", "juror said",
    "the council", "this council",
    "council concluded", "council decided",
    "council consensus", "council dissent",
    "draft says", "draft states", "draft claims",
    "the draft", "drafter said", "drafter argued",
    "peer review",
)


class LeakDetectedError(Exception):
    """Raised when a verification question would leak draft/framing/council content."""

    def __init__(self, kind: str, evidence: str, question_excerpt: str) -> None:
        super().__init__(
            f"Stage 3 leak filter blocked: {kind}. Evidence: {evidence!r}. "
            f"Question excerpt: {question_excerpt!r}"
        )
        self.kind = kind
        self.evidence = evidence


def _windows(text: str, n: int) -> Iterable[str]:
    """Yield n-word windows from text, lowercased."""
    if not text:
        return
    words = text.lower().split()
    if len(words) < n:
        return
    for i in range(len(words) - n + 1):
        yield " ".join(words[i:i + n])


def check_leak(
    question: str,
    *,
    operator_prompt: str,
    draft_text: str,
    framing_note: str,
    window: int = DEFAULT_WINDOW,
) -> None:
    """Raise LeakDetectedError if `question` smuggles forbidden content.

    Per-leak-type rules:
      - n-gram match: `window`-word verbatim windows from draft/framing,
        unless the same window also appears in operator_prompt
      - role marker: any ROLE_MARKERS substring, unless also in operator_prompt
    """
    q_lower = question.lower()
    op_lower = (operator_prompt or "").lower()

    # 1. Role markers
    for marker in ROLE_MARKERS:
        if marker in q_lower and marker not in op_lower:
            raise LeakDetectedError(
                kind=f"role-marker {marker!r}",
                evidence=marker,
                question_excerpt=question[:160],
            )

    # 2. n-gram overlap with draft
    for w in _windows(draft_text, window):
        if w in q_lower and w not in op_lower:
            raise LeakDetectedError(
                kind=f"{window}-word window from draft",
                evidence=w,
                question_excerpt=question[:160],
            )

    # 3. n-gram overlap with framing
    for w in _windows(framing_note, window):
        if w in q_lower and w not in op_lower:
            raise LeakDetectedError(
                kind=f"{window}-word window from framing",
                evidence=w,
                question_excerpt=question[:160],
            )


def check_inputs_clean(
    *,
    operator_prompt: str,
    verification_question: str,
    draft_text: str,
    framing_note: str,
    window: int = DEFAULT_WINDOW,
) -> None:
    """Defensive: check BOTH VerifierInput fields, not just the question.

    Two checks with different suppression rules:

      - `verification_question` may legitimately echo content from
        `operator_prompt` (the operator's own framing). So we suppress
        windows/markers that also appear in operator_prompt.
      - `operator_prompt` itself has NO prior legitimate context — it
        should not contain draft/framing windows or role markers under
        any circumstances. So we pass an empty string as the suppression
        baseline.

    Stage 3 passes the unmodified operator prompt today, so this is
    insurance against a future refactor that accidentally tampers with it.
    """
    # Check #1: the question, with operator_prompt as legitimate context.
    check_leak(verification_question, operator_prompt=operator_prompt,
               draft_text=draft_text, framing_note=framing_note, window=window)

    # Check #2: the operator_prompt itself, with NO suppression baseline.
    # If the operator_prompt contains "the draft says" or 8-word windows
    # from the draft, something upstream tampered with it.
    check_leak(operator_prompt, operator_prompt="",
               draft_text=draft_text, framing_note=framing_note, window=window)
