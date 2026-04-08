# AGENTS.md — Working in this repo

This file is a **travel guide**, not a law.
If anything here conflicts with the user's explicit instructions, the user wins.

> Instruction files shape behavior; the user determines direction.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## Tests

```bash
pytest tests/ -v
```

Always run tests before proposing commits. Never claim tests pass without running them.

---

## Safety and irreversibility

### Do not do these without explicit user confirmation
- Push to remote, create/close PRs or issues
- Delete or rewrite git history
- Modify dependency files in ways that change the lock file
- Change the closed-world assumption or has_fact semantics

### Preferred workflow
- Make changes in small, reviewable steps
- Run tests locally before proposing commits
- For any operation that affects external state, require explicit user confirmation

---

## Repository layout

```
verifier/
├── models.py          # Typed IR: Proposal, Fact, ConstraintRule, Verdict
├── compiler.py        # models → Z3 (has_fact + field_val predicates)
├── verifier.py        # Per-rule checking, closed-world, diagnostics
├── tests/
│   ├── test_scope_verifier.py   # Slice 0 basics
│   └── test_practical.py        # Concrete "does it have hands" suite
├── pyproject.toml
├── CLAUDE.md
├── AGENTS.md
└── PROVENANCE.md
```

---

## Coding conventions

- Python 3.11+, type hints, Pydantic v2 models
- pytest for testing
- Z3 constraints via compiler.py, never raw SMT in tests or verifier

---

## Invariants

1. Closed-world assumption: ungrounded (subject, field) pairs get `has_fact == false`
2. Every denial reports all failing rules, not a minimal subset
3. Warn-severity rules populate warnings but never cause denial
4. The verifier does not produce governance decisions

---

## What this is not

- Not a governor — verdicts only, governance is downstream
- Not a policy engine — rules come from domain systems
- Not a type system — field_val is stringly typed in slice 0 (known limitation)

---

## When you're unsure

Ask for clarification rather than guessing, especially around:
- Whether a new check belongs in the verifier or in governance
- Whether a fact should be modeled as presence vs. value
- Anything that changes the closed-world assumption

---

## Agent-specific instruction files

| Agent | File | Role |
|-------|------|------|
| Claude Code | `CLAUDE.md` | Full operational context, build details, conventions |
| Codex | `AGENTS.md` (this file) | Operating context + defaults |
| Any future agent | `AGENTS.md` (this file) | Start here |
