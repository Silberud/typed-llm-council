"""PR review bot (v0) — single-LLM forensic review on every PR.

Entry point: `python -m tools.pr_review --pr N [--dry-run]`.

v1 will swap the single-LLM call for the full multi-stage council
deliberation once Phases D + F land. The interface and output schema
are designed to be stable across that transition.
"""
