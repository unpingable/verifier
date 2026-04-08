# CLAUDE.md — Instructions for Claude Code

## What This Is

verifier: formal admissibility verifier sidecar that compiles typed IR into Z3 constraints and returns explainable verdicts.

## What This Is Not

- Not a governor — verdicts go downstream; governance decisions happen elsewhere
- Not a policy engine — it doesn't define rules, it checks them
- Not aware of domain internals — it only sees Proposal, Fact, and ConstraintRule

## Invariants

1. Closed-world assumption: missing facts fail closed, the solver cannot invent values
2. Every denial names every failing rule, not a minimal subset
3. Warn-severity rules never cause denial

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

- `compiler.py` — compiles models into Z3 (has_fact + field_val predicates, tracked assertions)
- `verifier.py` — per-rule checking with closed-world assumption, diagnostic layer
- `models.py` — typed IR: Proposal, Fact, ConstraintRule, Verdict, MissingFact
- `tests/` — pytest suite: scope verifier basics + practical "does it have hands" tests

## Conventions

- License: Apache-2.0
- Python 3.11+, type hints, Pydantic v2 models
- Testing: pytest, all tests must pass before commit
- No entry point yet — library consumed by downstream systems

## Don't

- Don't add governance logic to the verifier — it emits verdicts, period
- Don't use string sentinels for missing facts — use the has_fact predicate
- Don't minimize unsat cores — report all failing rules so governance sees everything
