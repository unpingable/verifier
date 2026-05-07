# CANDIDATES.md — Open questions and friction notes

Lightweight register of architectural questions surfaced during synthetic
workflow exercises, design review, or implementation.

Items here are **candidate / non-binding** — naming the question is not
authorization to build. Resolution requires explicit ratification.

When a candidate is resolved (built or rejected), migrate the conclusion
into CLAUDE.md / AGENTS.md / README.md as appropriate and remove the entry
here.

## Read of the register after Synthetic Workflows 1–3

The verifier has now survived three semantically different synthetic
domains — Standing grant (authority/lifecycle), release gate (mundane
constraint checklist), LLM claim promotion (basis/advisory/durable
boundary) — without schema change. The substrate property holds:

> *The verifier can express verdict structure without owning domain truth.*

Current read on the register, post-W3:

- **C-1 (Proposal shape).** Real and now hard signal. Three workflows,
  three different "natural" extension shapes. `Proposal` is carrying
  too much domain-specific shape in a fixed four-field coat. Probably
  actionable after W4.
- **C-2 (No variable binding).** Real, but **dangerous**. This is how a
  boring verifier turns into a tiny logic programming language wearing
  a fake mustache. Resist unless adapter ergonomics force it past
  endurance.
- **C-3 (`scope` collision).** Standing-side terminology debt. Out of
  scope for verifier.
- **C-4 (`claim_state` pre-gate).** Working. Positive signal.
- **C-5 (Required actor).** Keep required. Likely rename / redefine —
  candidates: `accountable_subject`, `initiator`, `claimant`,
  `authority_candidate`. The right name depends on the altitude.
- **C-6 (Open subject vocabulary).** Working. Positive signal.
- **C-7 (Verdict triad is basis-level).** Strong positive signal. Not
  decoration — actual model structure.
- **C-8 (No-basis fall-through).** Working. Positive signal.

**Discipline:** do not act on C-1 / C-5 before W4 (NQ suppression) lands.
Either W4 confirms the same wound, or it reveals a different one. Both
outcomes change what the right fix looks like.

---

## C-1: Proposal struct shape

**Current.** `Proposal = {action, actor, target, scope}` — fixed at four
fields.

**Surfaced by.**
- **Synthetic 1 (Standing grant check).** Workflow needed an `effect`
  dimension; encoded as `Fact(subject="proposal", field="effect")`. Splits
  proposal-shaped data across two channels.
- **Synthetic 2 (Release/merge gate).** Workflow's natural shape is
  `{action, repo, version}`. We mapped repo→target and version→scope,
  which works but stretches both words past the point where they pull
  their weight.
- **Synthetic 3 (LLM claim promotion).** Workflow's natural shape
  again carries an `effect` dimension (`durable_doctrine` vs
  `advisory_note`). Same encoding, same friction. Three workflows now
  pointing at the same shape question.

**Question.** Should `Proposal` grow extension fields (or a `dimensions`
map), or should all proposal-shaped data except action/actor/target live
in facts? Three workflows in, three different extension shapes
(`effect`, `repo`+`version`, `effect` again).

**Status.** Open, **signal now hard**. Three workflows pointing at the
same friction is no longer noise. Re-evaluate after workflow 4 (NQ
suppression) — but the shape of a probable resolution is becoming
visible.

**Directional lean (recorded for future review, not authorization to
build).** When this resolves, the likely move is **not** "add specific
fields like effect / repo / version" — that way lies taxonomy goblin.
More likely shape:

```
Proposal = {
  action,
  actor,
  target,
  context: map | string | object
}
```

or:

```
Proposal.core + Proposal.attributes
```

Wait until workflows 3–4 sweat before reaching for the wrench.

---

## C-2: No variable binding in atoms

**Current.** `ConstraintAtom` compares `(subject, field)` against a literal
value. Atoms cannot compare two atoms (e.g.
"`proposal.scope` must equal `actor.granted_scope`").

**Surfaced by.** Synthetic 1. Each Standing grant compiles to its own
per-grant rule with the grant's literal values baked into the rule body.
Tractable at small scale; not free at large scale.

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

**Status.** Open. Lean: actor-as-required is probably correct for an
admissibility checker — it keeps the audit chain whole — but worth
revisiting after the LLM-claim and NQ workflows surface their own
actor-shape preferences.

**Directional lean (recorded for future review, not authorization to
build).** Keep `actor` required. The issue likely is **not** "actor
should be optional" — it may be that `actor` semantically means
*accountable initiator* / *requesting system* / *authority claimant*
and the field name is too narrow. Rename or reshape later if needed,
but the audit-chain property of "every proposal names someone" is
worth preserving even when the value is synthetic. If you can't name
an accountable initiator, that's part of the finding.

**Candidate names** when this resolves (none ratified): `actor` (current),
`accountable_subject`, `initiator`, `claimant`, `authority_candidate`.
The right name depends on altitude — the verifier sees one role but
several upstream roles plausibly map to it. Decide which altitude the
field is operating at before renaming.

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
