# CLAUDE.md — Instructions for Claude Code

## What This Is

verifier: formal admissibility verifier sidecar that compiles typed IR into Z3 constraints and returns explainable verdicts.

Verifier is part of the Governor ecosystem, but it is not Governor-gated. It can be used directly as a Python library, a standalone CLI (`verifier-check`), or an MCP tool (`verifier-mcp`). All three surfaces funnel through `runner.run_payload` — one truth, three wrappers.

## What This Is Not

- Not a governor — verdicts go downstream; governance decisions happen elsewhere
- Not a policy engine — it doesn't define rules, it checks them
- Not aware of domain internals — it only sees Proposal, Fact, and ConstraintRule
- Not gated on the governor — runs standalone wherever it's useful

## Invariants

1. Closed-world assumption: missing facts fail closed, the solver cannot invent values
2. Every denial names every failing rule, not a minimal subset
3. Warn-severity rules never cause denial
4. Stale / revoked / expired evidence cannot produce `allowed` — it is filtered before the solver pass
5. The pre-gate is **scoped**: a non-current fact unrelated to any rule produces no diagnostic and no denial. No global stale-scanning.
6. `invalid_input` is a structural failure, not a member of the admissibility triad (`allowed | advisory | denied`)
7. Verdict is a pure function of `{proposal, facts, rules}` — order of facts and rules does not affect the verdict

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

- `models.py` — typed IR: Proposal, Fact (`claim_state`), ConstraintRule (`kind`, `basis_effect`), Verdict (triad + dimension_verdicts + stale_facts), MissingFact, StaleFact
- `compiler.py` — compiles models into Z3 (has_fact + field_val predicates, tracked assertions)
- `verifier.py` — per-rule checking with closed-world assumption, claim_state pre-gate, dimension projection, advisory aggregation
- `runner.py` — single dispatch (`run_payload`) shared by library, CLI, and MCP
- `cli.py` — `verifier-check` standalone CLI
- `mcp_server.py` — `verifier-mcp` NDJSON stdio server
- `adapters.py` — domain → Fact adapters (standing, continuity, ...)
- `tests/fixtures/` — canonical combined payloads (allowed/denied/invalid) shared across runner, CLI, and MCP tests
- `tests/test_invariants.py` — closed-world soul invariant
- `tests/test_dimensions.py` — per-kind verdict projection
- `tests/test_advisory.py` — verdict triad + basis_effect validation
- `tests/test_claim_state.py` — stale/revoked/expired pre-gate
- `tests/test_properties.py` — fact/rule permutation invariance
- `tests/test_parity.py` — cross-surface parity (library == CLI == MCP)

## Conventions

- License: Apache-2.0
- Python 3.11+, type hints, Pydantic v2 models
- Testing: pytest, all tests must pass before commit
- One core, three wrappers — never duplicate verification logic in CLI or MCP
- CLI/MCP stdout is JSON only; all logs and errors go to stderr
- A `denied` verdict is a successful run; CLI exit code is 0

## Don't

- Don't add governance logic to the verifier — it emits verdicts, period
- Don't use string sentinels for missing facts — use the has_fact predicate
- Don't minimize unsat cores — report all failing rules so governance sees everything
- Don't print to stdout from `mcp_server.py` — it corrupts the NDJSON transport
- Don't make a denied verdict a nonzero CLI exit code — denial is a valid result, not a crash
- Don't use `authorized` in verifier output — that word belongs to upstream authority kernels. The verifier classifies; it does not authorize.
- Don't repurpose `severity: warn` as advisory — they're different animals. Warning means "this rule did not block." Advisory means "this basis can be heard but cannot support action." Use `kind="basis"` + `basis_effect="advisory"`.
- Don't globally scan for stale facts — the claim_state pre-gate is scoped to facts referenced by a rule. Spooky-action-at-a-distance diagnostics are worse than no diagnostic.
- Don't fold `invalid_input` into the admissibility triad — it's a schema/transport failure, not a verdict on the proposal.
