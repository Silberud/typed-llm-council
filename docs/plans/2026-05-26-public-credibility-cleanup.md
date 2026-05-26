# Public Credibility Cleanup Implementation Plan

> **For Hermes:** This plan was produced after a four-pass audit loop. The recommendation set stabilized for three consecutive loops (loops 2, 3, and 4) with the same five findings: `README_PHASE_E_STATUS`, `E2_LIVE_VALIDATION_STALE`, `REVIEW_TRAIL_STALE`, `TEST_TOTALS_STALE`, and `PUBLIC_FLIP_STATUS_STALE`.

**Goal:** Bring the now-public `typed-llm-council` repository's public-facing documentation into exact alignment with the current implementation, live-validation state, and GitHub public status.

**Architecture:** No product-code behavior changes are required. The repository's technical core is already green (`55/55` structural tests, blocking ruff, latest CI green). This plan updates documentation surfaces that still carry stale transitional language from private staging, pre-live-validation E.2, or pre-public flip status.

**Tech Stack:** Markdown documentation, GitHub repository metadata, Python package project with pytest/ruff CI.

---

## Audit Evidence

### Repository state verified

- Repo visibility: `PUBLIC`
- Discussions: enabled
- GitHub description: `Stage-3 verifier-isolation prototype for a multi-model LLM council; full pipeline in progress.`
- Current HEAD during audit: `76b817d`
- Recent public-cleanup/live-validation commits present:
  - `ceb3bf0` public-facing residual private-staging cleanup
  - `400a67d` live comparator validation test
  - `76b817d` roadmap/issues cross-linking and E.2 live-validation reflection

### Quality gates verified before implementation

- `pytest -q orchestrator/tests` -> `55 passed`
- `ruff check .` -> `All checks passed!`
- Latest GitHub Actions on public repo -> green

### Stabilized recommendation loop

Loop output was stable for three consecutive no-change iterations:

1. Loop 1: 5 findings discovered.
2. Loop 2: same 5 findings, no change.
3. Loop 3: same 5 findings, no change.
4. Loop 4: same 5 findings, no change.

Stable finding set:

1. `README_PHASE_E_STATUS` — README top status sentence says E.0+E.1 only while table says E.2 is implemented/live-validated.
2. `E2_LIVE_VALIDATION_STALE` — docs still say E.2 live validation is pending/open even though `test_comparator_live.py` exists and README says `2/2` live comparator tests pass.
3. `REVIEW_TRAIL_STALE` — README adversarial review trail is commit-specific and stale after subsequent public-launch/live-validation commits.
4. `TEST_TOTALS_STALE` — `docs/hermes_findings_status.md` test totals omit the live comparator tests.
5. `PUBLIC_FLIP_STATUS_STALE` — `docs/hermes_findings_status.md` still reads like public flip is pending/insufficiently closed in its open-items language.

---

## Task 1: Correct README Phase E status sentence

**Objective:** Make the README status header match the Phase E status table and current E.2 live-validation state.

**Files:**
- Modify: `README.md`

**Change:**

Replace the status sentence:

```markdown
**v2.3.0 ships Phase A + Phase B + Phase E (E.0 + E.1) of a 9-phase plan.** Be explicit about that.
```

with:

```markdown
**v2.3.0 ships Phase A + Phase B + Phase E (E.0 + E.1 + E.2 opt-in) of a 9-phase plan.** Be explicit about that.
```

**Verification:**

Run:

```bash
grep -n "v2.3.0 ships" README.md
```

Expected: the line includes `E.0 + E.1 + E.2 opt-in`.

---

## Task 2: Replace stale README adversarial-review trail

**Objective:** Remove dangling commit-specific wording that became stale after public-launch and live-validation commits.

**Files:**
- Modify: `README.md`

**Current problem:** The paragraph still says Pass 3 ended at `f05f1b9 + this one`, while newer commits exist and E.2 live validation has landed.

**Replacement paragraph:**

```markdown
**Adversarial review trail:** Hermes Agent (GPT-5.5) reviewed the repository across multiple passes from 24–26 May 2026. Pass 1 raised 20 numbered findings against the initial private-staging release; subsequent hardening passes closed 19/20 and addressed the remaining framing caveat with runtime checks and more precise language. Later passes cleaned public-facing docs, validated the real E.2 comparator against live Claude on synthetic SUPPORT / CONTRADICT / NOT_RELATE cases, and corrected launch metadata. Per-finding status: [`docs/hermes_findings_status.md`](docs/hermes_findings_status.md). The review trail is preserved as part of the design-feedback story, not as a substitute for independent human review.
```

**Verification:**

Run:

```bash
grep -n "Adversarial review trail" README.md
grep -n "f05f1b9.*this one" README.md || true
```

Expected: first command prints the new paragraph; second prints nothing.

---

## Task 3: Update `docs/hermes_findings_status.md` open-items section

**Objective:** Make the findings-status file reflect that the repository is already public and that E.2 live comparator validation has been performed.

**Files:**
- Modify: `docs/hermes_findings_status.md`

**Current problem:** The file's open-items section still lists live comparator smoke as open and does not clearly close the public flip.

**Replacement section:**

Replace the section beginning:

```markdown
## What remains genuinely OPEN (post-public, 2026-05-26)
```

through the test totals block with the following:

```markdown
## What remains genuinely OPEN (post-public, 2026-05-26)

1. **Phases C / D / F / G / H** of the 9-phase plan. Roadmap at `ROADMAP.md`; tracking Issues #2–#6 are open.
2. **Independent external review.** The Hermes review chain was adversarial-AI review by a different model identity, not human review. Outside human or third-party adversarial review is welcome via Discussions or Issues.
3. **Broader E.2 comparator validation.** The real comparator has now passed a small live-Claude smoke (`tests/_live/test_comparator_live.py`) covering SUPPORT / CONTRADICT / NOT_RELATE on synthetic answers. Larger validation on real Stage 3 transcripts remains future work.

Public flip status: **complete** on 2026-05-26. Discussions are enabled and the repo is visible publicly.

## Test totals across passes

- v2.3.0 (initial): 24/24 structural + 1 live Stage 3 integration
- After Pass 1: 39/39 structural + 1 live Stage 3 integration
- After Pass 2 / public cleanup: 55/55 structural + 1 live Stage 3 integration + 2/2 live comparator tests
```

**Verification:**

Run:

```bash
grep -n "Public flip status" docs/hermes_findings_status.md
grep -n "2/2 live comparator" docs/hermes_findings_status.md
grep -n "Live integration smoke for the real CoVe comparator" docs/hermes_findings_status.md || true
```

Expected: first two commands print matches; third prints nothing.

---

## Task 4: Update stale CHANGELOG E.2 limitation

**Objective:** Make `CHANGELOG.md` agree with the live comparator test that was added after the earlier public-launch polish.

**Files:**
- Modify: `CHANGELOG.md`

**Changes:**

1. In Hardening Pass 2, replace:

```markdown
Default stays placeholder; real mode opt-in until live
validation accumulates.
```

with:

```markdown
Default stays placeholder; real mode remains opt-in. Later live smoke
validation landed in `400a67d`.
```

2. Add a new changelog section after Hardening Pass 3:

```markdown
## Public live-validation follow-up — commits `400a67d`, `76b817d` (2026-05-26)

- `400a67d` — added `orchestrator/tests/_live/test_comparator_live.py`, validating the real Claude comparator on hand-crafted SUPPORT / CONTRADICT / NOT_RELATE cases without spending Kimi quota.
- `76b817d` — cross-linked ROADMAP phases to Issues #2–#6 and reflected E.2 live-validation status in README.
```

3. In current known limitations, replace:

```markdown
- **Phase E.2 real comparator:** unit-tested with mocked Claude; **live validation pending**. Default remains the placeholder.
```

with:

```markdown
- **Phase E.2 real comparator:** unit-tested and smoke-tested against live Claude on synthetic SUPPORT / CONTRADICT / NOT_RELATE cases. Default remains the placeholder; broader validation on real Stage 3 transcripts is future work.
```

**Verification:**

Run:

```bash
grep -n "live validation pending" CHANGELOG.md || true
grep -n "Public live-validation follow-up" CHANGELOG.md
grep -n "broader validation on real Stage 3 transcripts" CHANGELOG.md
```

Expected: first command prints nothing; second and third print matches.

---

## Task 5: Run documentation contradiction scan

**Objective:** Confirm no stale phrases remain in the public docs.

**Files:**
- Read only.

**Command:**

```bash
rg -n "private staging|before flipping public|Then we go public|live validation pending|f05f1b9.*this one|37/37|argv prompt visibility|not implemented yet" README.md CHANGELOG.md docs/hermes_findings_status.md docs/design_notes.md docs/operator_setup.md DISCUSSION_SEED.md ROADMAP.md
```

**Expected interpretation:**

- `initial private staging` in CHANGELOG is acceptable if it refers to the historical baseline.
- `not implemented yet` is acceptable when referring to Phases C/D/F/G/H.
- No stale E.2 live-validation or dangling public-flip language should remain.

---

## Task 6: Verify quality gates

**Objective:** Prove the docs-only patch did not break tests or lint.

**Commands:**

```bash
ruff check .
pytest -q orchestrator/tests
```

Expected:

```text
All checks passed!
55 passed
```

Also check Git state:

```bash
git diff --stat
git diff -- README.md CHANGELOG.md docs/hermes_findings_status.md
```

Expected: only documentation changes.

---

## Task 7: Commit and push

**Objective:** Land public credibility cleanup on the public repository.

**Commands:**

```bash
git add README.md CHANGELOG.md docs/hermes_findings_status.md docs/plans/2026-05-26-public-credibility-cleanup.md
git commit -m "docs: align public credibility trail after live validation"
git push origin docs/public-credibility-pass
```

If working directly on `main` is allowed, push to main after confirming branch policy. Otherwise create a PR:

```bash
gh pr create \
  --title "docs: align public credibility trail after live validation" \
  --body "## Summary
- Align README Phase E status with E.2 opt-in live-validation state
- Update Hermes findings status for completed public flip and live comparator smoke
- Remove stale CHANGELOG language saying E.2 live validation is pending
- Add forensic execution plan documenting the stabilized recommendation loop

## Verification
- ruff check .
- pytest -q orchestrator/tests
"
```

---

## Success Criteria

- README says Phase E includes E.2 opt-in.
- README review trail has no dangling `this one` phrasing.
- `docs/hermes_findings_status.md` says public flip is complete.
- `docs/hermes_findings_status.md` no longer lists the real comparator live smoke as open.
- CHANGELOG no longer says E.2 live validation is pending.
- Forensic plan exists under `docs/plans/`.
- `ruff check .` passes.
- `pytest -q orchestrator/tests` passes.
- Changes are committed and pushed to GitHub.
