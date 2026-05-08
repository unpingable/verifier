# CANDIDATES.md — Open questions and friction notes

Lightweight register of architectural questions surfaced during synthetic
workflow exercises, design review, or implementation.

Items here are **candidate / non-binding** — naming the question is not
authorization to build. Resolution requires explicit ratification.

When a candidate is resolved (built or rejected), migrate the conclusion
into CLAUDE.md / AGENTS.md / README.md as appropriate and remove the entry
here.

## Read of the register after Synthetic Workflows 1–4 + C-1 patch

The verifier has now survived four semantically different synthetic
domains — Standing grant (authority/lifecycle), release gate (mundane
constraint checklist), LLM claim promotion (basis/advisory/durable
boundary), NQ suppression (operationally rich gate). All friction
concentrated on Proposal shape (C-1). The substrate property holds:

> *The verifier can express verdict structure without owning domain truth.*

Current read on the register:

- **C-1 (Proposal shape).** **Resolved in schema 0.3.0.** Added
  `Proposal.attributes: dict[str, str | int | bool]` for
  domain-specific extension data; core spine (action/actor/target/scope)
  preserved as the audit grammar. All synthetic fixtures migrated;
  no rule changes needed. Migrated to "Resolved" section below.
- **C-2 (No variable binding).** Real, but **dangerous**. Two friction
  shapes seen so far: per-grant rule duplication (W1) and pre-computed
  boolean facts for interval comparison (W4). Both workarounds work.
  This is how a boring verifier turns into a tiny logic programming
  language wearing a fake mustache. Resist.
- **C-3 (`scope` collision).** Standing-side terminology debt. Out of
  scope for verifier.
- **C-4 (`claim_state` pre-gate).** Working. Positive signal.
- **C-5 (Required actor).** Doctrine partially landed: actor docstring
  in models.py now defines actor as "accountable initiator / system
  submitting the proposal." Optional rename (to `accountable_subject`
  etc.) deferred — the docstring clarification absorbed the W2/W3/W4
  friction without renaming. Open as a deferred-rename candidate.
- **C-6 (Open subject vocabulary).** Working. W2 used tests/parity/etc;
  W4 used maintenance_window/operator_ack/witness/etc. The schema
  accommodates naturally.
- **C-7 (Verdict triad is basis-level).** Strong positive signal. Not
  decoration — actual model structure.
- **C-8 (No-basis fall-through).** Working. Confirmed in two
  independent workflows now (W2 release gate, W4 NQ suppression). Pure
  constraint workflows are first-class.

**Wind tunnel verdict:** the IR survived four unrelated semantic
temperatures, the one load-bearing wound (C-1) was diagnosed precisely
and patched without redesigning rules, dimensions, arithmetic, or
actor semantics. Restraint paid rent.

---

## C-1: Proposal struct shape (RESOLVED — schema 0.3.0)

**Resolution.** Added `Proposal.attributes: dict[str, str | int | bool]`
in schema 0.3.0. Domain-specific extension data lives in attributes;
the four-field audit spine (action/actor/target/scope) stays put.
Attribute keys appear in the grounded set as `(proposal, key)` so rule
atoms reference them the same way they reference core fields.

**Boundary preserved.** Attributes are *proposed intent*. Facts remain
*external evidence*. Rules can refer to both, but the channels do not
collapse into each other.

**Migration outcome.** All four synthetic workflows (W1 Standing, W3
LLM claim promotion, W4 NQ suppression) migrated to use attributes
instead of `Fact(subject="proposal", field=...)`. No rule changes
needed. W2 (release gate) had no proposal-shaped facts to migrate.

**Historical context (preserved as evidence trail).** The friction was
diagnosed across four workflows with four different "natural"
extension shapes — `effect` (W1, W3), `repo+version` (W2, partial),
`duration+reason` (W4). Forcing them into facts on `subject="proposal"`
collapsed the proposal-intent vs external-evidence channels. The
wind-tunnel exercise specifically existed to surface this friction
before patching it; the patch was minimum-scope (one new field, one
default-empty dict) and did not touch rules / dimensions / arithmetic
/ actor semantics.

---

## C-2: No variable binding in atoms

**Current.** `ConstraintAtom` compares `(subject, field)` against a literal
value. Atoms cannot compare two atoms (e.g.
"`proposal.scope` must equal `actor.granted_scope`").

**Surfaced by.**
- **Synthetic 1 (Standing grant check).** Each Standing grant compiles
  to its own per-grant rule with the grant's literal values baked into
  the rule body. Tractable at small scale; not free at large scale.
- **Synthetic 4 (NQ suppression).** Different shape of the same
  friction: comparing two intervals (proposal.duration vs
  window.duration) requires a pre-computed boolean fact
  (`duration_within_window`). The adapter does the arithmetic; the
  verifier checks the result for equality. The IR is deliberately
  arithmetic-free.

**Question.** Is per-grant rule duplication acceptable indefinitely, or
should the IR grow some form of variable binding / atom-pair comparison?

**Status.** Open. Closed-world + no-variables is a design choice (clean
semantics, tractable solver). Leaving unless adapter ergonomics force
otherwise.

**Directional lean (recorded for future review, not authorization to
build).** This is real but **dangerous** to fix. Granting variable
binding is how a boring verifier turns into a tiny logic programming
language wearing a fake mustache. The current adapter pain (per-grant
literal rules) is acceptable cost. Resist unless workflows past W4
demonstrate ergonomic failure that no other restructuring can fix.

---

## C-3: Vocabulary collision on `scope`

**Current.** `Proposal.scope` is the operating scope of an action (e.g.,
`"prod"`, or a path subset like `"agent_gov/docs"`). The existing Standing
adapter's `granted_scope` fact is mapped from the upstream crate's
`scope.action` field — which actually means "what action is granted."

**Surfaced by.** Synthetic 1. Two different semantic axes wearing the same
English word "scope."

**Status.** This is **Standing-side terminology debt, not verifier-side**.
The verifier's `Proposal.scope` is fine. Flag for upstream cleanup; no
verifier change.

---

## C-4: `claim_state` pre-gate (positive signal)

**Current.** `Fact.claim_state ∈ {current, stale, revoked, expired}`.
Non-current facts are filtered before the solver pass. Scoped diagnostic
surfaces via `Verdict.stale_facts` for facts referenced by a rule.

**Surfaced by.** Synthetic 1's expired-grant case mapped directly onto
this machinery: grant lifecycle → `claim_state`, scoped pre-gate produced
the right verdict (denied) and the right diagnostic (`stale_facts`
populated, attributed to the standing rules that referenced the
expired fields).

**Status.** Working as intended. Recorded as a positive data point for
future workflows; no follow-up.

---

## C-5: Required actor on Proposal

**Current.** `Proposal.actor` is required (Pydantic `min_length=1`).

**Surfaced by.**
- **Synthetic 2 (Release/merge gate).** Chatty's release proposal had
  no actor — "tag a release" is more an event than a directed action.
  We invented `actor="release-pipeline"` to satisfy the schema, but
  the value carries no semantic weight in any of the rules.
- **Synthetic 3 (LLM claim promotion).** Domain has multiple plausible
  actor roles: claimant (in `claim.source`), proposer (in
  `Proposal.actor`), authority (implicit in basis rules), publisher (in
  `Proposal.target`). The single `actor` field collapses some of these.
  Different sweat than W2 — not "actor missing," but "actor ambiguous
  among co-existing roles." Reinforces the directional lean below.

**Question.** Should `Proposal.actor` be optional, or is the verifier
right to insist that every proposal name a responsible party (even if
synthetic)?

**Status.** Partially landed in schema 0.3.0. Actor remains required
(min_length=1). The Proposal.actor docstring now defines the field as:

> *accountable initiator / system submitting the proposal. Not
> necessarily a human, not necessarily the metaphysical agent of
> causation — just the named party standing behind the request.*

This absorbed the W2/W3/W4 friction without renaming. After the
docstring landing, `actor="release-pipeline"` is no longer "fake to
satisfy schema" — it's the correctly-named accountable initiator for
that proposal.

**Open as deferred-rename candidate.** Whether to rename the field to
`accountable_subject`, `initiator`, `claimant`, or `authority_candidate`
remains open. Not pursued in the C-1 patch — the docstring fix was
the minimum-scope move, and a rename touches every adapter and rule
that references `actor`. Defer until a workflow demonstrates the name
is actively obstructive (rather than just historically narrow).

---

## C-6: Open subject vocabulary (positive signal)

**Current.** `Fact.subject` is a non-empty string. The docstring lists
`actor / target / proposal / system / policy` as examples but does not
constrain.

**Surfaced by.** Synthetic 2 used subjects `tests / parity / readme / git`
without friction. The schema accommodated naturally.

**Status.** Working as intended. Minor: the docstring example list could
be expanded to make clear that subjects are an open vocabulary. No
behavior change required.

---

## C-7: Verdict triad does what it was designed for (positive signal)

**Current.** `allowed | advisory | denied` admissibility triad, with
`advisory` produced when the only basis fired is one with
`basis_effect="advisory"`.

**Surfaced by.** Synthetic 3 (LLM claim promotion) is the workflow
specifically built to test this. The advisory case (LLM-source claim
proposing advisory_note) produces `status="advisory"` with **zero rule
failures and zero warnings** — proving the verdict is basis-level
machinery, not severity-level. The denied cases prove that even with
an independent receipt present, an LLM-source claim cannot bridge to
durable doctrine (Rule A and Rule B are orthogonal gates that compose
cleanly).

**Status.** Working as intended. The "heard, not authorized" channel
that motivated chatty's design exists and behaves as specified. Strong
positive signal — recorded for future reference, no follow-up.

---

## C-8: No-basis fall-through is restraint, not omission (positive signal)

**Current.** When zero basis rules are submitted, `_aggregate_status`
returns `allowed` (or `denied` per failures) without forcing the
workflow into a basis-shaped frame.

**Surfaced by.** Synthetic 2 (Release/merge gate) was a pure
constraint workflow — no basis rules at all. The verifier did not
require one and did not contort the verdict semantics. Pure constraint
checking remains a first-class use of the IR.

**Status.** Working as intended. Worth pinning explicitly because the
restraint is rare: the verifier is not forcing every workflow into
Governor-shaped metaphysics.
