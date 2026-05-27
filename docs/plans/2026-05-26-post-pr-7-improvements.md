# Post PR-#7 Improvements Implementation Plan

> **Status:** Plan landed alongside changes in the same PR. Audit loop stabilised after three consecutive zero-finding rounds (rounds 10, 11, 12 with strict structural bar).

**Goal:** Build on the workflow pattern Hermes Agent established in PR #7 (forensic audit → formal plan doc → PR-driven change → quality gates verified). Formalise the `docs/plans/` convention, add public-repo best-practice surfaces (`SECURITY.md`, runnable `examples/`), and close one remaining doc-consistency item the audit surfaced.

**Architecture:** No product-code behaviour changes. Adds convention scaffolding (`docs/plans/TEMPLATE.md`), one new top-level file (`SECURITY.md`), one new directory (`examples/`), and updates `CONTRIBUTING.md` + `CHANGELOG.md`. Existing tests, CI, ruff all stay green.

**Tech Stack:** Markdown documentation, GitHub repository metadata, Python package project with pytest/ruff CI.

---

## Audit Evidence

### Repository state verified before planning

- Latest origin/main: `666902b` (PR #7 merged by Andrjushapa / Hermes Agent).
- `pytest -q orchestrator/tests` → `55 passed`.
- `ruff check .` → `All checks passed!`.
- Latest GitHub Actions on `666902b` → green.

### Stabilised audit findings (after 3 consecutive zero-finding rounds)

1. **`CHANGELOG_STALE_THIS_COMMIT`** — `CHANGELOG.md:91` reads `## Public-launch polish — *this commit* (2026-05-26)`, but that section is no longer "this commit" (several commits have landed since). The historical commit SHA is `ceb3bf0`.
2. **`PLAN_TEMPLATE_MISSING`** — Hermes's PR #7 added `docs/plans/2026-05-26-public-credibility-cleanup.md` which is a great structural template, but the convention is implicit. Future contributors won't know to follow it.
3. **`CONTRIBUTING_NO_PLAN_CONVENTION`** — `CONTRIBUTING.md` doesn't mention the `docs/plans/` workflow at all.
4. **`SECURITY_POLICY_MISSING`** — Public repo has no `SECURITY.md`. GitHub's surface check flags this; it's standard hygiene for an MIT-licensed repo accepting outside contribution.
5. **`NO_RUNNABLE_EXAMPLES`** — Visitors who don't read the test suite have no way to see Stage 3 verifier-isolation in action. An `examples/` directory with a small runnable demo lowers the activation energy for design-feedback contributors.

### What is NOT in scope for this PR (deliberately deferred)

- **Python 3.13 in CI matrix.** Hermes proved it works locally (`55 passed` under 3.13) but adding a CI job needs its own validation cycle.
- **Branch protection on `main`.** Operator decision; would block direct pushes (which the maintainer has been using). Not a code change.
- **GitHub Pages / hosted docs.** Needs Jekyll/MkDocs setup; out of scope here.
- **Tagged release (`v2.3.0`).** Needs operator decision on release semantics.
- **More "good first issue" labels.** Should be added when there's a real candidate task.

---

## Task 1: Fix `CHANGELOG.md` stale `*this commit*` reference

**Objective:** Replace the stale `*this commit*` wording with the actual commit SHA `ceb3bf0`.

**Files:**
- Modify: `CHANGELOG.md`

**Change:**

```diff
- ## Public-launch polish — *this commit* (2026-05-26)
+ ## Public-launch polish — commit `ceb3bf0` (2026-05-26)
```

**Verification:**

```bash
grep -n "this commit" CHANGELOG.md
```

Expected: no matches (or only matches inside docs/plans/ historical quotes).

---

## Task 2: Add `docs/plans/TEMPLATE.md`

**Objective:** Codify the structure Hermes used in PR #7 so future plans follow it consistently.

**Files:**
- Add: `docs/plans/TEMPLATE.md`

**Content:** A template with placeholders for:
- Status (loop-stability note)
- Goal
- Architecture/Context
- Audit Evidence
- Per-task breakdown (Objective / Files / Change / Verification)
- Success Criteria

**Verification:**

```bash
test -f docs/plans/TEMPLATE.md
```

---

## Task 3: Update `CONTRIBUTING.md` with `docs/plans/` convention

**Objective:** Document the plan-doc-then-PR workflow so contributors know how non-trivial changes are expected to land.

**Files:**
- Modify: `CONTRIBUTING.md`

**Change:** Add a section "Plan-then-PR workflow" between "Where to start" and "Tests":

> For any change beyond a one-line fix, follow the convention established by PR #7:
> 1. Open a branch.
> 2. Write a plan doc at `docs/plans/YYYY-MM-DD-<short-slug>.md` using `docs/plans/TEMPLATE.md`. The plan should include an audit-loop summary (stabilised after N zero-finding rounds), per-task breakdown, and success criteria.
> 3. Make changes in the same branch.
> 4. Open a PR. The PR description should link to the plan doc.
> 5. Quality gates: `ruff check .` clean, `pytest -q orchestrator/tests` green, no doc inconsistencies the plan was supposed to fix still standing.

**Verification:**

```bash
grep -n "Plan-then-PR workflow" CONTRIBUTING.md
grep -n "docs/plans/TEMPLATE.md" CONTRIBUTING.md
```

---

## Task 4: Add `SECURITY.md`

**Objective:** Standard public-repo disclosure policy.

**Files:**
- Add: `SECURITY.md`

**Content:**
- Scope: this repo's source code.
- Reporting channel: `igor.silberud@gmail.com` (private).
- Response timeline: best-effort acknowledgement within 7 days; no bounty.
- Out of scope: third-party model providers (Anthropic / Google / OpenAI / Alibaba / xAI / Moonshot) — report to them.
- Note: this repo handles model API keys via macOS Keychain; never write a key into the source tree.

**Verification:**

```bash
test -f SECURITY.md
grep -n "igor.silberud@gmail.com" SECURITY.md
```

---

## Task 5: Add `examples/` with runnable Stage 3 demo

**Objective:** A visitor who clones the repo and runs one file should see Stage 3 verifier-isolation in action without reading the test suite.

**Files:**
- Add: `examples/README.md`
- Add: `examples/stage3_verification_demo.py`

**Content of demo:** Calls `stage3_cove_verify` directly with:
- A small operator prompt
- A hand-crafted draft with 2–3 verifiable claims
- A `MockKimi` adapter that returns canned `VerifierAnswer`s

So the example is fully runnable without needing Moonshot/Kimi credentials. It demonstrates:
- How `VerifierInput` is constructed
- How the leak filter sits between the decomposer and Kimi
- What the comparator output looks like

**Verification:**

```bash
python3 examples/stage3_verification_demo.py
```

Expected: prints questions, mock answers, and the comparator result. Exits 0.

**Note:** The demo uses a `MockKimi` and a `mock_decomposer` so it does not burn quota. It's a structural demo, not a live integration test.

---

## Task 6: Quality gates

**Commands:**

```bash
ruff check .
pytest -q orchestrator/tests
python3 examples/stage3_verification_demo.py
```

Expected:
- `All checks passed!`
- `55 passed`
- example runs cleanly, exits 0.

---

## Task 7: Commit, push, open PR

**Commands:**

```bash
git checkout -b improve/conventions-and-discoverability
git add CHANGELOG.md docs/plans/2026-05-26-post-pr-7-improvements.md \
        docs/plans/TEMPLATE.md CONTRIBUTING.md SECURITY.md \
        examples/README.md examples/stage3_verification_demo.py
git commit -m "docs+infra: post-PR-#7 conventions, security policy, examples"
git push -u origin improve/conventions-and-discoverability

gh pr create \
  --title "docs+infra: post-PR-#7 conventions, security policy, examples" \
  --body "..."
```

---

## Success Criteria

- `CHANGELOG.md` no longer says `*this commit*` outside historical plan quotes.
- `docs/plans/TEMPLATE.md` exists and matches the structure of the PR-#7 plan.
- `CONTRIBUTING.md` documents the `docs/plans/` convention with link to `TEMPLATE.md`.
- `SECURITY.md` exists at repo root.
- `examples/stage3_verification_demo.py` runs cleanly with no Kimi credentials.
- `ruff check .` passes.
- `pytest -q orchestrator/tests` shows 55 passed.
- PR opened, CI green, merged.
