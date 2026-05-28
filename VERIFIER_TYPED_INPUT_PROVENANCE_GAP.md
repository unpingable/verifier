# Gap: typed input provenance

**Status:** named surface. Construction forcing-case-gated.

This is not a "candidate / non-binding" hedge. The surface is named
because retrofit cost is predictably high: the constellation is
linking (wicket consuming verifier verdicts as evidence, NQ supplying
substrate facts, Standing decisions referenced by receipts, Continuity
reliance records flowing through), and these tools will all speak
through `Fact.source` whether we shape it deliberately or accidentally.

**Name broadly, build narrowly.** The boundary contract below is
doctrine starting now. The metadata shape is the named design. Field
implementation lands when the first consumer concretizes its calling
shape — but the design is not an open question, and adapters/consumers
arriving in the meantime should plan against this shape rather than
invent their own.

> *If you wait too long to name a surface, implementation will name it
> badly for you.*

## Scope

How facts and rules derived from upstream constellation tools — NQ,
Standing, Continuity, Wicket, or any other — enter verifier input
**without laundering their origin or standing**.

The verifier is already careful about what it does internally:
closed-world assumption, scoped `claim_state` pre-gate, every failing
rule reported, no global stale-scanning, verdict pure under
permutation. The gap is one step upstream: the IR is type-correct,
but `Fact.source` is a free-form string. That is enough for boring
single-source workflows. It is not enough for constellation use,
where a fact might be any of:

- An NQ substrate observation
- A Standing decision receipt
- A Continuity reliance record
- A Wicket admissibility verdict consumed as evidence
- A prior verifier verdict re-entered as evidence

These need *distinguishable provenance*, not just labels.

## Boundary contract (doctrine — applies now)

These are the constraints any future provenance work has to honor.
They are also the constraints in force *today*, before any metadata
extension ships. Adapters and consumers writing against the verifier
today should already behave as if these were enforced; the schema
will catch up.

1. **Cooked, not fetched.** The verifier receives `proposal + facts + rules`. It does not fetch truth. It does not call NQ / Standing / Continuity / Wicket on the hot path. Any provenance must arrive on the IR; the verifier must not chase it.
2. **Missing evidence remains denial.** Provenance metadata cannot turn a missing fact into a grounded one. Closed-world stays closed-world.
3. **Stale / revoked / expired remains non-grounding.** Provenance metadata cannot rescue a non-current fact. The `claim_state` pre-gate is the final word on whether a fact reaches the solver.
4. **Verdicts are evidence, not authority.** A verifier verdict consumed as input by a downstream tool (e.g. wicket) is a `Fact`, with its own `source`, its own `claim_state`, and its own lifecycle. Re-entering an `allowed` verdict as evidence does not import authority.
5. **No upstream calls.** If a downstream wants to ratify upstream evidence, that ratification happens *before* the call to the verifier. The verifier is stateless and offline.
6. **`authorized` stays reserved.** That word belongs to upstream authority kernels (e.g. the Lean Authority kernel). The verifier classifies admissibility; provenance metadata does not promote admissibility to authorization.
7. **The provenance channel does not become a policy channel.** Provenance metadata describes *where a fact came from*. It does not let rules express *what makes a source acceptable* — that judgment is the caller's, applied before the fact reaches the verifier.

## Provenance metadata shape (named design)

A fact in constellation use carries the following metadata. This is
the shape future adapters and rule writers should plan against; the
fields named here are the ones the contract requires.

```json
{
  "subject": "nq:labelwatch",
  "field": "sqlite_wal_state",
  "value": "present",
  "claim_state": "current",
  "source": "nq",
  "source_receipt": "sha256:...",
  "standing_decision_ref": "sha256:...",
  "continuity_relied_on": [
    {
      "memory_id": "mem_xyz",
      "content_hash": "sha256:...",
      "evaluation_time": "..."
    }
  ]
}
```

Field-by-field:

- **`source`** — the named upstream tool / kernel. Stays a string, but
  becomes a vocabulary the verifier can reason about (e.g.
  `"nq" | "standing" | "continuity" | "wicket" | "verifier" | …`).
  Today's free-form usage stays compatible.
- **`source_receipt`** — content-addressed pointer to the upstream
  artifact that produced this fact (NQ witness receipt, wicket
  verdict receipt, prior verifier verdict, …). `sha256:` prefix per
  wicket convention.
- **`standing_decision_ref`** — when the speaker's standing was
  evaluated upstream, the receipt of that decision. The verifier
  does not re-evaluate standing; it just records that the caller
  did.
- **`continuity_relied_on`** — when the upstream computation relied
  on durable memory, the list of memory records relied on, with
  content hashes and evaluation times. Lets a downstream auditor
  detect stale-memory laundering.

**What this is not:** a policy DSL. Rules cannot say "deny if
`source != "standing"`" — that would re-introduce the upstream-call
problem in the form of source policy. Provenance metadata is for
*attribution and audit*, not for *rule-level source filtering*. If a
caller wants to refuse facts from certain sources, the caller filters
the fact list before invoking the verifier.

## Build triggers (construction gate, narrow)

Any one of these concretizes the implementation:

- An actual downstream consumer (wicket, governor, etc.) wires
  verifier output as evidence and needs the verifier to refuse on
  missing or contradictory provenance.
- A workflow surfaces a real ambiguity that the free-form `source`
  string cannot disambiguate.
- A regression where two facts with the same `(subject, field, value)`
  but different provenance produce the wrong verdict.

When a trigger fires, the wind-tunnel methodology applies: run 3–4
synthetic consumer workflows of varied semantic temperature before
patching, let the friction concentrate, and keep the remediation
narrow. The design above is the starting point, not the final word —
adapter friction may rename or restructure fields.

## No remote verifierd

The three current surfaces (library, CLI, MCP stdio) all funnel
through `runner.run_payload`. A network-exposed verifier daemon would
re-introduce the same auth / standing / source-attribution problem
this gap exists to anticipate, with the extra burden of being a
remote attack surface.

Do not build `verifierd` unless an actual downstream forces it, and
even then prefer making the existing surfaces work harder first.

## Composes with

- The wind-tunnel methodology (see `feedback_wind_tunnel` in
  project memory): if metadata implementation triggers, run a
  wind tunnel before patching.
- CANDIDATES.md — IR-shape questions; this gap is the cross-tool
  shape question, distinct scope.
- The C-1 resolution principle (CLAUDE.md): `Proposal.attributes`
  is proposed intent; `Fact` is external evidence. Provenance
  metadata lives on Fact, where it belongs.

## Keeper

> *Verifier can prove a proposal violates supplied rules.
> It cannot prove the world supplied the right facts.*

The verifier is a small theorem goblin. Useful. Not sovereign. The
provenance seam is what keeps it from being misread as the latter.
