# Release process

This document describes how a version is cut. Source of truth for "what's currently in flight" is `ROADMAP.md`; source of truth for "what changed in each version" is `CHANGELOG.md`.

## Versioning policy

The project follows **semver-ish** with these conventions:

- **Major (`X.0.0`)** — breaking change to the public API (`orchestrator/schemas/`, `orchestrator/adapters/base.py`) or to the on-disk layout (`~/.h5r-council/`).
- **Minor (`2.X.0`)** — a phase from the 9-phase plan (A–H) ships, or a non-breaking new public surface.
- **Patch (`2.3.X`)** — bugfix, documentation, infrastructure, or hardening pass that doesn't change shipped behaviour.

The major version tracks the council's spec version (`v2.3` = spec v2.2 implementation as of the 2026-05-26 public launch). Future spec revisions bump the major.

## Pre-flight checklist

Before cutting a release:

1. `git checkout main && git pull` — be on tip of main.
2. `ruff check .` — green.
3. `pytest -q orchestrator/tests` — green.
4. `python3 examples/stage3_verification_demo.py` — exits 0.
5. `gh pr list --state open` — no open PRs you want bundled.
6. `CHANGELOG.md` — has a section for the version about to be cut; commit-by-commit summary written; "Public-launch polish — *this commit*"-style stale refs replaced with concrete SHAs.
7. ROADMAP — phase statuses match what just shipped.
8. README — version in `# Typed LLM Council (vX.Y.Z)` heading matches the tag about to be cut.
9. `CITATION.cff` — `version:` and `date-released:` fields updated.

## Cutting the release

```bash
# Replace X.Y.Z with the actual version.
git tag -a vX.Y.Z -m "vX.Y.Z — <one-line summary>"
git push origin vX.Y.Z

# Create the GitHub release. Notes pulled from CHANGELOG section.
gh release create vX.Y.Z \
  --title "vX.Y.Z — <one-line summary>" \
  --notes-file <(awk '/^## vX\.Y\.Z/,/^## /{print}' CHANGELOG.md | sed '$d')
```

After release:

1. Verify the release page renders correctly: `gh release view vX.Y.Z`.
2. If this release closes any tracking issues (e.g. Phase C in #2), close them with a link to the release.
3. Post a comment on Discussion #1 (Show and tell) summarising the release.
4. If breaking, post a separate Discussion announcing the migration path.

## Hot-fix on a released version

For an urgent fix on a released version `vX.Y.Z` while `main` has unreleased work:

1. `git checkout -b hotfix/X.Y.(Z+1) vX.Y.Z`
2. Cherry-pick or write the minimal fix; plan doc not required for one-line fixes (per `CONTRIBUTING.md`).
3. PR → squash-merge → cut `vX.Y.(Z+1)`.
4. Merge the hotfix branch back into `main` to keep history consistent.

## Yank / un-release

If a tag is published in error:

1. `gh release delete vX.Y.Z --cleanup-tag` — removes the GH release and the underlying tag.
2. Don't reuse the version number; bump to the next patch.
3. Post on Discussion #1 explaining what was broken and what the next release will contain.

## Tag signing (not yet adopted)

GPG-signed tags are a future enhancement; current releases are unsigned. When adopted, this section will describe the maintainer's signing key and `git tag -s` usage.
