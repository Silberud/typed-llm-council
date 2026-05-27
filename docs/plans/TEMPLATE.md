# <Title> Implementation Plan

> **Status:** Stabilisation note. Example: "Audit loop stabilised after three consecutive zero-finding rounds (rounds N, N+1, N+2 with strict structural bar)."

**Goal:** One-paragraph statement of what this plan delivers and why.

**Architecture:** One-paragraph statement of the kind of change (e.g., "No product-code behaviour change; pure documentation alignment" or "New stage added to the orchestrator pipeline"). Mention any cross-cutting concerns (config, schema, tests).

**Tech Stack:** Markdown / Python / GitHub Actions / pytest / ruff — whichever apply.

---

## Audit Evidence

### Repository state verified before planning

- Latest origin/main: `<sha>` (last merged PR, if any).
- `pytest -q orchestrator/tests` → `N passed`.
- `ruff check .` → `All checks passed!`.
- Latest GitHub Actions on `<sha>` → green.

### Stabilised audit findings (after K consecutive zero-finding rounds)

1. **`SHOUTY_FINDING_TAG_1`** — what's wrong, with file:line reference.
2. **`SHOUTY_FINDING_TAG_2`** — …

Each finding gets a tag that the per-task headings reference.

### What is NOT in scope for this PR (deliberately deferred)

- Item A — why deferred.
- Item B — why deferred.

---

## Task 1: <short imperative title>

**Objective:** One sentence.

**Files:**
- Modify: `path/to/file.md`
- Add: `path/to/new_file.py`

**Change:**

```diff
- old line
+ new line
```

(or a fuller code block for new files)

**Verification:**

```bash
grep -n "expected substring" path/to/file.md
```

Expected: …

---

## Task N: <next task>

(repeat the pattern above)

---

## Task <last>: Quality gates

**Commands:**

```bash
ruff check .
pytest -q orchestrator/tests
# any task-specific verification commands
```

Expected: all green.

---

## Task <last+1>: Commit, push, open PR

**Branch:** `<type>/<short-slug>`

**Commands:**

```bash
git checkout -b <branch>
git add <files>
git commit -m "<type>: <short description>"
git push -u origin <branch>
gh pr create --title "..." --body "..."
```

---

## Success Criteria

- Bullet-list of measurable, verifiable outcomes — one per task's verification.
- `ruff check .` passes.
- `pytest -q orchestrator/tests` shows N passed.
- PR opened, CI green, merged.
