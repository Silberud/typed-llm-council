# Council Quickstart

How to run a real multi-vendor PR review with [`/review-pr`](../.claude/commands/review-pr.md) in under 5 minutes (assuming you already have the prerequisite CLIs installed and authenticated).

## What you'll get

A real review where three different LLM vendors (OpenAI / Google / Alibaba) each independently vote on the PR, plus Claude as chairman synthesising their verdicts — committed to your repo as a structured markdown artefact. See [`docs/reviews/24-iter1.md`](reviews/24-iter1.md) for an example.

## Prerequisites (one-time, per machine)

| CLI | Provider | Auth method | Install |
|---|---|---|---|
| `claude` | Anthropic (chairman) | OAuth via Claude Code Pro/Max subscription | `npm install -g @anthropic-ai/claude-code`, then `claude` (`/login` once if needed) |
| `codex` | OpenAI (Architect — GPT-5.5) | OAuth via ChatGPT Pro subscription | OpenAI Codex CLI — see [openai.com/codex-cli](https://openai.com/index/codex/) |
| `gemini` | Google (Researcher — Gemini 3.1 Pro) | OAuth (no API key needed; uses Google account quota) | `npm install -g @google/gemini-cli`, then `gemini` (interactive login on first use) |
| `ollama` | Local (Analyst — Qwen 3.6 35B) | None (local model, no auth) | `brew install ollama` then `ollama pull qwen3.6:35b-a3b-coding-nvfp4` |
| `gh` | GitHub | OAuth or PAT | `brew install gh && gh auth login` |
| `jq` | (helper for JSON) | none | `brew install jq` |

Verify all are installed:

```bash
for c in claude codex gemini ollama gh jq; do
  which $c && $c --version 2>&1 | head -1
done
```

Optional but recommended:

```bash
brew install coreutils      # provides `gtimeout` for per-member timeouts
export TIMEOUT_BIN=gtimeout # enable timeouts in the slash command
```

## Run a review

```bash
cd ~/llm-council-public        # any same-repo PR works
claude                         # opens Claude Code session
# inside:
/review-pr 24                  # replace 24 with any open PR number
```

What happens (≈2 minutes wallclock):

1. Claude (you) fetches the PR via `gh`.
2. Three parallel Bash calls fan out to `codex`, `gemini`, `ollama` — each receives the same brief (role-specific persona + diff) and returns a structured `VERDICT:` line.
3. Claude synthesises the three verdicts (majority vote with conservative tie-breaking).
4. Claude writes `docs/reviews/<PR>-iter<K>.md`.
5. Claude shows you the verdict and asks via `AskUserQuestion` what to do next (merge / commit-only / comment-and-label).
6. Claude executes your choice via `gh`.

## What if one vendor fails?

Each member can return `DROPPED:` if its CLI errors or times out. The council continues with the remaining members. **Minimum 2 voters required** for a valid synthesis (v0 baseline; spec §6 Stage 2's 3-voter rule applies once Grok un-stubs).

## Anti-bias claim, mechanically

The repo's central thesis is that **multi-vendor deliberation breaks single-vendor bias** that any individual model would have inherited from its training corpus and RLHF preferences. The `/review-pr` slash command implements this concretely:

- Each member runs in a **different vendor's process** (separate provider, separate model weights, separate alignment training).
- Each member gets the **same prompt** — convergence across vendors is signal; divergence is also signal.
- The chairman (Claude) is the synthesizer but **doesn't get a vote** — it doesn't get to advocate for its own opinion.

See [`docs/reviews/24-iter1.md`](reviews/24-iter1.md) for the first real demonstration: 3/3 vendors caught the same bug independently, plus one vendor (Gemini) caught a bonus finding the other two missed. That second-finding asymmetry is exactly what vendor diversity buys you.

## Cost

Zero new $ — the slash command uses your existing subscriptions:

- `claude` → Claude Code Pro/Max subscription quota
- `codex` → ChatGPT Pro subscription
- `gemini` → free Gemini OAuth quota (or paid Gemini API if exhausted)
- `ollama` → local CPU/GPU only (no cloud)

If you blow a vendor's quota, that member returns `DROPPED:` and the council continues with the rest. No per-token API charges.

## Limitations (v0)

- **Majority vote, not AceMAD-weighted.** When Phase F (Stage 4 AceMAD aggregation) ships, the slash command will swap to peer-prediction-weighted Brier-scored verdicts. For now: simple count with conservative tie-breaking.
- **No CoVe verification step.** Kimi (the verifier seat) is in the architecture but not yet wired into `/review-pr`. Deferred to v1.
- **No D3 advocate/juror role rotation.** All three members are pure jurors in v0. Deferred to v1.
- **No FOCUS drift escalation.** If the council can't converge across iterations, there's no automatic escalation. Deferred to v1 (Phase G).
- **Manual invocation only.** No automatic re-review on new commits, no scheduled cron. The operator types `/review-pr <N>` when they want a review.
- **Grok (Skeptic) still stubbed.** See CG-001 in [`docs/operator_setup.md`](operator_setup.md). When xAI opens an OAuth path on X Premium+, Grok joins the council and the outcome space goes from 9 back to 12 per spec.

## Reading the artefact

Each `docs/reviews/<PR>-iter<K>.md` contains:

- **Triage** — files, lines, author trust, invariant files touched
- **Security pre-check** — regex tripwire hits + the chairman's evaluation
- **Member verdicts** — each vendor's raw response (verdict + reasoning + required actions)
- **Aggregation** — vote counts, entropy note
- **Chairman synthesis** — narrative explanation of how the verdict was reached
- **Decision** — APPROVE / APPROVE-WITH-MINOR-MODIFY / MODIFY / REJECT / NEEDS-MAINTAINER
- **Required actions** — de-duplicated blocker list across members
- **Soft suggestions** — non-blocking observations

Reviews are **advisory** — the maintainer makes every merge decision.

## Customising the prompt

The slash command file ([`.claude/commands/review-pr.md`](../.claude/commands/review-pr.md)) is plain markdown with YAML frontmatter. Persona hints per member are inline. To adjust:

1. Edit the file (e.g. tighten the Architect's persona, change the verdict format).
2. Open a PR with the change.
3. The change gets reviewed by the council itself — recursively. The Council reviews changes to its own prompt.

That recursion is the audit trail.
