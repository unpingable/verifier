# verifier

Formal admissibility verifier sidecar using Z3. Takes proposals, facts, and constraint rules; returns explainable verdicts.

Verifier is part of the Governor ecosystem, but it is not Governor-gated. It can be used directly as a Python library, a standalone CLI, or an MCP tool.

## What it does

- Checks whether a proposed action is admissible given grounded facts and named constraint rules
- Returns all failing rules (not a minimal unsat core) so governance sees every violation
- Distinguishes missing evidence from negative evidence via closed-world assumption
- Classifies admissibility along named dimensions (basis / precedence / standing / constraint) without conflating them
- Excludes aged-out evidence (`stale | revoked | expired`) from the solver pass while surfacing it as a scoped diagnostic

## What this is not

- Not a governor — it emits verdicts, not governance decisions
- Not a policy engine — rules are compiled from upstream domain systems
- Not a replacement for standing, continuity, or custody — it only sees their typed IR

## Entry points

Three surfaces, one core (`runner.run_payload`). A verdict produced through one
surface is bit-for-bit identical to one produced through the others.

### Library

```python
from runner import run_payload

verdict = run_payload({
    "proposal": {...},
    "facts":    [...],
    "rules":    [...],
})
```

### CLI

```bash
verifier-check input.json
cat input.json | verifier-check -
```

JSON-only on stdout. Diagnostics on stderr. Exit codes are semantic:

- `0` — verification ran; verdict printed (this includes `denied` — a denied
  verdict is a successful run, not a crash)
- `2` — invalid usage or malformed input
- `3` — internal error

### MCP

```bash
verifier-mcp
```

NDJSON over stdio. One tool: `verify`, taking `{proposal, facts, rules}`. Wire
into `.mcp.json`:

```json
{
  "mcpServers": {
    "verifier": {
      "command": "/path/to/.venv/bin/verifier-mcp"
    }
  }
}
```

## Verdict vocabulary

The verifier emits one of three **admissibility** verdicts:

- `allowed`  — every deny-rule passed, and either there are no basis rules in play or at least one **actionable basis** fired and held
- `advisory` — every deny-rule passed, but only **advisory bases** fired (heard, but not authority to act)
- `denied`   — a deny-rule failed, OR basis rules were submitted but none fired

Plus one **structural** status, which is not part of the admissibility triad:

- `invalid_input` — the input was internally contradictory; rules were not evaluated. This is a schema/transport failure, not a verdict on the proposal.

`authorized` is reserved for upstream authority kernels (e.g. the Lean Authority kernel). The verifier classifies admissibility; it does not authorize.

### Rule kinds

Every `ConstraintRule` carries a `kind` (default `constraint`). The verifier groups rules by kind to produce per-dimension diagnostics in `Verdict.dimension_verdicts`:

| Kind         | Purpose                                                        |
|--------------|----------------------------------------------------------------|
| `basis`      | Rules establishing authority to act. May carry `basis_effect`. |
| `precedence` | Rules about ordering / prior decisions.                        |
| `standing`   | Rules about who is permitted in scope.                         |
| `constraint` | Ordinary domain rules that don't fit a named dimension.        |

A basis rule may declare `basis_effect: actionable | advisory`. Advisory bases push the verdict to `advisory`; they cannot produce `allowed`. `basis_effect` is only valid on `kind: basis`; it is a schema error elsewhere.

### Claim state

Every `Fact` carries a `claim_state` (default `current`). Non-current facts (`stale | revoked | expired`) are excluded from the solver pass — they cannot ground a rule, prove a basis, or contradict a current fact. If a non-current fact's `(subject, field)` is referenced by a rule, it surfaces as a `StaleFact` diagnostic so the consumer knows their input had aged-out evidence in scope. Non-current facts unrelated to any rule are silently ignored — there is no global stale-scanning.

## Invariants

1. Absence of a required fact is denial, not satisfiable imagination
2. Every denial names the specific rules that caused it
3. The verifier never invents values for ungrounded fields
4. Stale / revoked / expired evidence cannot produce `allowed`
5. Verdict.status is invariant under permutation of the input fact and rule lists

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
