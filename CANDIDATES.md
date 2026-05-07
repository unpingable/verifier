# CANDIDATES.md — Open questions and friction notes

Lightweight register of architectural questions surfaced during synthetic
workflow exercises, design review, or implementation.

Items here are **candidate / non-binding** — naming the question is not
authorization to build. Resolution requires explicit ratification.

When a candidate is resolved (built or rejected), migrate the conclusion
into CLAUDE.md / AGENTS.md / README.md as appropriate and remove the entry
here.

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

**Question.** Should `Proposal` grow extension fields (or a `dimensions`
map), or should all proposal-shaped data except action/actor/target live
in facts? Two workflows now point at the same friction with different
extension shapes (`effect` vs `repo`+`version`).

**Status.** Open, signal strengthening. Two workflows in. Re-evaluate
after workflows 3–4.

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

**Surfaced by.** Synthetic 2 (Release/merge gate). Chatty's release
proposal had no actor — "tag a release" is more an event than a directed
action. We invented `actor="release-pipeline"` to satisfy the schema, but
the value carries no semantic weight in any of the rules.

**Question.** Should `Proposal.actor` be optional, or is the verifier
right to insist that every proposal name a responsible party (even if
synthetic)?

**Status.** Open. Lean: actor-as-required is probably correct for an
admissibility checker — it keeps the audit chain whole — but worth
revisiting after the LLM-claim and NQ workflows surface their own
actor-shape preferences.

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
