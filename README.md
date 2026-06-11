# verifier

A boundary checker between measurement and claim.

The verifier does not decide whether the world is true. It checks whether a
system's emitted claims are licensed by the evidence it actually has —
taking proposals, facts, and named constraint rules, compiling them to Z3,
and returning explainable verdicts.

It is not an oracle. It is not a judge. It is a constraint gate against
epistemic overreach: before a monitor, labeler, report, or agentic
workflow turns observations into findings, and findings into claims,
the claim must pass admissibility.

Verifier is part of the Governor ecosystem, but it is not Governor-gated.
It can be used directly as a Python library, a standalone CLI
(`verifier-check`), or an MCP tool (`verifier-mcp`).

> *The verifier can express verdict structure without owning domain truth.*
>
> *Verifier can prove a proposal violates supplied rules.*
> *It cannot prove the world supplied the right facts.*

The first keeper is the architectural property — the verifier does
not grow domain opinions. The second is the consumer-facing warning —
a verifier verdict is evidence, not authority.

For constellation consumers (NQ, Standing, Continuity, Wicket, …):
the boundary contract and the named provenance-metadata shape live in
[VERIFIER_TYPED_INPUT_PROVENANCE_GAP.md](./VERIFIER_TYPED_INPUT_PROVENANCE_GAP.md).
That document specifies the invariants in force today and the
metadata shape adapters should plan against when consumers wire in.

## 30-second specimen

A deploy request that *looks* fully credentialed — the actor was granted `prod`
scope — but the grant **expired before the spend**. Conventional auth says yes; the
verifier denies, and the verdict says exactly why.

`examples/stale-standing-denied.json`:

```json
{
  "proposal": { "action": "deploy", "actor": "worker-a", "target": "service/api", "scope": "prod" },
  "facts": [
    { "subject": "actor", "field": "granted_scope", "value": "prod",
      "source": "standing:grant-101", "claim_state": "expired" }
  ],
  "rules": [
    { "rule_id": "standing.scope_match", "kind": "standing",
      "description": "Actor's granted scope must match the proposal scope",
      "require": [ { "subject": "actor", "field": "granted_scope", "op": "eq", "value": "prod" } ] }
  ]
}
```

```bash
verifier-check examples/stale-standing-denied.json
```

Verdict (abridged — `dimension_verdicts` and empty lists omitted; the full,
test-pinned output is `examples/stale-standing-denied.verdict.json`):

```json
{
  "status": "denied",
  "failed_rules": [
    { "rule_id": "standing.scope_match",
      "description": "Actor's granted scope must match the proposal scope",
      "severity": "deny", "kind": "standing" }
  ],
  "used_facts": [],
  "stale_facts": [
    { "rule_id": "standing.scope_match", "subject": "actor", "field": "granted_scope",
      "source": "standing:grant-101", "claim_state": "expired" }
  ]
}
```

The grant existed. It even matched. It was just **expired at decision time**, so it
could not ground the rule (invariant 4), `used_facts` is empty (the aged-out grant
was dropped, not counted), and the denial *names the rule* while *surfacing the
dropped evidence* (`stale_facts`) instead of failing opaquely. That is the whole tool
in fifteen seconds: not "we said no," but "your credential was real, stale, and here
is the field that proves it." (Exit code is `0` — a denied verdict is a successful
run, not a crash.)

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

### Proposal shape

```
Proposal = {
  action:     str,           # the verb being proposed
  actor:      str,           # accountable initiator / system submitting the proposal
  target:     str,           # the thing being acted upon
  scope:      str,           # the operating scope of the action
  attributes: dict[str, str | int | bool],  # domain-specific extension data
}
```

The four core fields are the **audit spine** — every proposal names
someone trying to do something to something in some scope. `attributes`
is where domain-specific shape goes (effect, version, duration, reason,
repo, …) so adapters don't have to smuggle proposal-shaped data through
`Fact(subject="proposal", field=...)`. Attribute keys appear in the
grounded set as `(proposal, key)` so rule atoms reference them the same
way they reference the core fields.

The boundary that schema 0.3.0 protects: **attributes are proposed
intent; facts are external evidence.** Rules can refer to both, but the
two channels do not collapse into each other.

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

Thirty seconds to a verdict:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# the specimen from the top of this README — prints a `denied` verdict, exit 0
verifier-check examples/stale-standing-denied.json
```

Develop / run the suite (the example above is pinned by `tests/test_examples.py`,
so the README's verdict can't silently drift from what the code emits):

```bash
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
