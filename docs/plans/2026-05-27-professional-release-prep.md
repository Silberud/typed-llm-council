# v2.3.0 Professional-Release Scaffolding Implementation Plan

> **Status:** Plan audit-loop stabilised after 7 consecutive zero-correction rounds (rounds 6–12). Each round added new perspectives (security, accessibility, governance, sustainability, legal, i18n, perf/SEO, onboarding, testing rigor, error pathways, contributor simulation, comparability, anti-patterns, AI-policy, portability, supply-chain, time-delayed view, minimal-viable scope, redundancy, file-by-file scrutiny).

**Goal:** Promote the repo from "publicly readable" to "professionally maintainable" before cutting v2.3.0. Adds the standard GitHub community-health surfaces (Issue/PR templates, CODEOWNERS, Dependabot, CITATION, CoC), wires pre-commit, documents the release process, and finishes by cutting the v2.3.0 tag + GitHub release.

**Architecture:** No product-code behaviour change. Pure scaffolding + metadata + release.

**Tech Stack:** Markdown, YAML (Issue forms, Dependabot, pre-commit, CITATION), GitHub repository metadata, `gh` CLI for release/labels.

---

## Audit Evidence

### Repository state verified before planning

- Latest origin/main: `377e43e` (PR #8 merged, squash).
- `pytest -q orchestrator/tests` → `55 passed`.
- `ruff check .` → `All checks passed!`.
- `examples/stage3_verification_demo.py` → 5 agreements, exits 0.
- README already has CI / License / Python badges (no badge work needed).
- Repo already has topics: `chain-of-verification`, `cove`, `llm`, `llm-as-judge`, `mixture-of-agents`, `multi-agent`.
- Default labels present: `bug`, `documentation`, `enhancement`, `help wanted`, `good first issue`, `question`, `duplicate`, `invalid`, `wontfix`.

### Stabilised audit findings

1. **`NO_ISSUE_TEMPLATES`** — Issues open as blank; first-time reporters have no scaffolding. The 5 design questions in README §"Looking for feedback on" deserve a structured form so feedback comes in comparable shape.
2. **`NO_PR_TEMPLATE`** — PR #7 (Hermes) and PR #8 established a Plan-doc convention; a PR template should remind contributors to link the plan doc + check quality gates.
3. **`NO_CODEOWNERS`** — Review-request auto-assignment to `@Silberud` not wired.
4. **`NO_DEPENDABOT`** — pip + github-actions security/version drift not monitored.
5. **`NO_COC`** — Public repo accepting outside contribution should have a code of conduct.
6. **`NO_CITATION`** — Research-adjacent project (CoVe, peer-prediction) merits a CITATION.cff for academic referencing.
7. **`NO_PRE_COMMIT`** — Contributors can push code that fails CI ruff; a pre-commit hook catches it locally first.
8. **`NO_RELEASE_PROCESS_DOC`** — First public release coming; future releases need a documented procedure.
9. **`NO_HYGIENE_SECTION`** — README doesn't surface the new community files (CoC / CITATION / SECURITY / CONTRIBUTING) anywhere visible.
10. **`NO_V2.3.0_TAG`** — Spec-version 2.3 of the council; no git tag, no GH release.
11. **`REPO_DESCRIPTION_TIGHT`** — Current GH `description` field is functional but could be tightened for the social card.
12. **`ISSUES_UNLABELLED`** — Issues #2–#6 are the deferred-phase tracking issues but carry only default labels; phase labels would help triage.
13. **`DISCUSSION_1_NEEDS_RELEASE_PING`** — Seed Discussion #1 doesn't yet mention v2.3.0 release artefacts.

### What is NOT in scope for this PR (deliberately deferred)

- **Python 3.13 in CI matrix** — Hermes proved local 55/55 under 3.13; CI matrix expansion is its own validation cycle.
- **Branch protection on `main`** — operator decision.
- **GitHub Pages / hosted docs** — needs Jekyll/MkDocs setup.
- **GPG-signed tags** — personal-project scale; can adopt later.
- **`docs/faq.md`** — useful but not urgent; will land when Q's accumulate.
- **`GOVERNANCE.md`** — single-maintainer; CODEOWNERS covers it.
- **License headers in source files** — MIT doesn't require them.
- **Third-party license inventory** — deps listed in `pyproject.toml` is enough.

---

## Task 1: Issue templates (YAML form)

**Objective:** Replace blank-Issue UX with structured forms.

**Files:**
- Add: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Add: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Add: `.github/ISSUE_TEMPLATE/config.yml` (turns off blank Issues; contact link → Discussions; contact link → SECURITY.md)
- Pre-existing (kept as-is): `.github/ISSUE_TEMPLATE/design-feedback.yml` — covers the 5 README design questions; checked during audit and confirmed correct, so not duplicated.

**Verification:**

```bash
ls .github/ISSUE_TEMPLATE/
```

Expected: `bug_report.yml`, `feature_request.yml`, `design-feedback.yml`, `config.yml`. After merge, the New Issue page on GitHub should show 3 form options + 2 contact links (Discussions + Security).

---

## Task 2: PR template

**Objective:** Codify the plan-doc-link + quality-gates-checklist habit established by PRs #7 and #8.

**Files:**
- Add: `.github/pull_request_template.md`

**Verification:** After merge, opening a new PR should pre-fill the body.

---

## Task 3: CODEOWNERS

**Objective:** Auto-tag the maintainer for review on every PR.

**Files:**
- Add: `.github/CODEOWNERS` — `* @Silberud`

---

## Task 4: Dependabot (pip + github-actions)

**Objective:** Weekly automated security/version-drift PRs for both pip dependencies and pinned action versions.

**Files:**
- Add: `.github/dependabot.yml`

---

## Task 5: Code of Conduct

**Objective:** Contributor Covenant 2.1, contact = `igor.silberud@gmail.com` (same as SECURITY.md).

**Files:**
- Add: `CODE_OF_CONDUCT.md`

---

## Task 6: CITATION.cff

**Objective:** Allow GitHub's "Cite this repository" widget + provide a stable citation handle for academic write-ups.

**Files:**
- Add: `CITATION.cff`

**Schema:** [Citation File Format 1.2.0](https://citation-file-format.github.io/).

---

## Task 7: pre-commit config

**Objective:** Local `ruff check` hook so contributors don't waste CI minutes on lint failures.

**Files:**
- Add: `.pre-commit-config.yaml`

---

## Task 8: Release process doc

**Objective:** Document how releases get cut (semver decisions, tag, GH release, CHANGELOG promotion) so v2.4.0+ follow the same pattern.

**Files:**
- Add: `docs/release_process.md`

---

## Task 9: README "Project conventions" section

**Objective:** Add a section near the bottom of README pointing to CoC, CITATION, SECURITY, CONTRIBUTING, release process, plan-doc convention.

**Files:**
- Modify: `README.md`

---

## Task 10: CHANGELOG v2.3.0 section

**Objective:** Promote the existing public-launch entry to a proper `## v2.3.0 — 2026-05-27` heading, summarising what landed.

**Files:**
- Modify: `CHANGELOG.md`

---

## Task 11: Quality gates

**Commands:**

```bash
ruff check .
pytest -q orchestrator/tests
python3 examples/stage3_verification_demo.py
```

Expected: all green.

---

## Task 12: PR

**Branch:** `prep/v2.3.0-professional-release`

**Commands:**

```bash
git add -A
git commit -m "prep: v2.3.0 professional-release scaffolding"
git push -u origin prep/v2.3.0-professional-release
gh pr create --title "..." --body "..."
```

---

## Task 13: Merge, tag v2.3.0, GH release

**Commands:**

```bash
gh pr merge <N> --squash --delete-branch
git checkout main && git pull
git tag -a v2.3.0 -m "v2.3.0 — first public release"
git push origin v2.3.0
gh release create v2.3.0 --title "v2.3.0 — First public release" --notes-file <(...)
```

---

## Task 14: Repo metadata + labels + Discussion comment

**Commands:**

```bash
# Tighten description; topics already cover key terms.
gh repo edit Silberud/typed-llm-council --description "..."

# Create phase labels (idempotent with || true).
for p in C D F G H; do
  gh label create "phase:$p" --color "0e8a16" --description "Phase $p of the 9-phase plan" || true
done

# Apply to deferred-phase issues.
gh issue edit 2 --add-label "phase:C"
gh issue edit 3 --add-label "phase:D"
gh issue edit 4 --add-label "phase:F"
gh issue edit 5 --add-label "phase:G"
gh issue edit 6 --add-label "phase:H"

# Announce on Discussion #1.
gh api repos/Silberud/typed-llm-council/discussions/1/comments -f body="v2.3.0 released …"
```

---

## Success Criteria

- `.github/ISSUE_TEMPLATE/` has 3 YAML forms + `config.yml`.
- `.github/pull_request_template.md` exists.
- `.github/CODEOWNERS`, `.github/dependabot.yml` exist.
- `CODE_OF_CONDUCT.md`, `CITATION.cff`, `.pre-commit-config.yaml` exist.
- `docs/release_process.md` exists.
- README has a "Project conventions" section pointing to the above.
- CHANGELOG has a `## v2.3.0 — 2026-05-27` heading.
- `ruff check .` passes, `pytest -q orchestrator/tests` shows 55 passed, example exits 0.
- PR opened, CI green, squash-merged.
- Git tag `v2.3.0` pushed; GitHub release `v2.3.0` published.
- GH repo description tightened; phase labels created + applied to issues #2–#6.
- Discussion #1 has a release-announcement comment.
