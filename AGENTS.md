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

## Ecosystem position

Verifier is part of the Governor ecosystem, but it is not Governor-gated.
It can be used directly as a Python library, a standalone CLI (`verifier-check`),
or an MCP tool (`verifier-mcp`). All three surfaces funnel through
`runner.run_payload` — one truth, three wrappers. Never duplicate verification
logic in the CLI or MCP server; add to `runner.py` instead.

## Repository layout

```
verifier/
├── models.py          # Typed IR: Proposal, Fact (claim_state), ConstraintRule
│                      #   (kind, basis_effect), Verdict (triad +
│                      #   dimension_verdicts + stale_facts)
├── compiler.py        # models → Z3 (has_fact + field_val predicates)
├── verifier.py        # Per-rule checking, closed-world, claim_state pre-gate,
│                      #   dimension projection, advisory aggregation
├── runner.py          # run_payload — single dispatch shared by all surfaces
├── cli.py             # verifier-check standalone CLI
├── mcp_server.py      # verifier-mcp NDJSON stdio server
├── adapters.py        # Domain → Fact adapters
├── tests/
│   ├── fixtures/                 # Canonical combined payloads (allowed/denied/invalid)
│   ├── golden/                   # Wire-format goldens (drift detector)
│   ├── test_runner.py            # In-process dispatch
│   ├── test_cli.py               # Subprocess CLI round-trips
│   ├── test_mcp.py               # In-process MCP dispatch
│   ├── test_parity.py            # Cross-surface verdict identity (lib == CLI == MCP)
│   ├── test_invariants.py        # Closed-world soul invariant
│   ├── test_dimensions.py        # Per-kind verdict projection
│   ├── test_advisory.py          # Verdict triad + basis_effect validation
│   ├── test_claim_state.py       # Stale/revoked/expired pre-gate
│   ├── test_properties.py        # Permutation invariance + determinism
│   ├── test_scope_verifier.py    # Slice 0 basics
│   └── test_practical.py         # Concrete "does it have hands" suite
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
5. Stale / revoked / expired evidence cannot produce `allowed` (filtered before solver)
6. claim_state pre-gate is scoped to facts referenced by a rule — no global stale-scanning
7. `invalid_input` is structural failure, not part of the admissibility triad (`allowed | advisory | denied`)
8. Verdict.status is invariant under permutation of facts and rules

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
- Anything that changes the verdict triad or its aggregation rules
- Whether the verifier should adopt a Lean-side concept (verdict-vocabulary porting requires design review, not just implementation)

---

## Agent-specific instruction files

| Agent | File | Role |
|-------|------|------|
| Claude Code | `CLAUDE.md` | Full operational context, build details, conventions |
| Codex | `AGENTS.md` (this file) | Operating context + defaults |
| Any future agent | `AGENTS.md` (this file) | Start here |
