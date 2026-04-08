# verifier

Formal admissibility verifier sidecar using Z3. Takes proposals, facts, and constraint rules; returns explainable verdicts.

## What it does

- Checks whether a proposed action is admissible given grounded facts and named constraint rules
- Returns all failing rules (not a minimal unsat core) so governance sees every violation
- Distinguishes missing evidence from negative evidence via closed-world assumption

## What this is not

- Not a governor — it emits verdicts, not governance decisions
- Not a policy engine — rules are compiled from upstream domain systems
- Not a replacement for standing, continuity, or custody — it only sees their typed IR

## Invariants

1. Absence of a required fact is denial, not satisfiable imagination
2. Every denial names the specific rules that caused it
3. The verifier never invents values for ungrounded fields

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## Architecture

```
proposal + facts + rules
        │
        ▼
  ┌───────────┐
  │  compiler  │  models.py → Z3 constraints
  │            │  has_fact + field_val predicates
  └─────┬─────┘
        │
        ▼
  ┌───────────┐
  │  verifier  │  per-rule check with closed-world assumption
  │            │  diagnostic: missing_facts, failed_rules, warnings
  └─────┬─────┘
        │
        ▼
     Verdict
```

## License

Licensed under Apache-2.0.
