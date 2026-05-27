# Examples

Runnable demonstrations of what Typed LLM Council currently implements. These are designed to **run without any API credentials** — they force mock adapters/decomposers and placeholder comparators where needed so you can see the pipeline shape without burning model quota.

## What's here

| File | What it shows |
|---|---|
| `stage3_verification_demo.py` | The Phase E (CoVe verifier) pipeline end-to-end: mock decomposition → real leak filter → mock verifier → forced placeholder comparator. Pure structural demo — no real LLM calls. |

## Running

From the repo root, after `pip install -e ".[dev]"`:

```bash
python3 examples/stage3_verification_demo.py
```

Each example exits 0 on success and prints a human-readable trace of what happened at each stage. They double as smoke tests of the public API.

## What's NOT here (yet)

End-to-end `council <prompt>` examples — those require Phases C/D to ship (see [`ROADMAP.md`](../ROADMAP.md)). When the full council pipeline lands, additional examples will be added here.

If you want to see a *live* test (real Claude + real Kimi), look at `orchestrator/tests/_live/` — but be aware those burn real model quota.
