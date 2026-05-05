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

**Surfaced by.** Synthetic 1 (Standing grant check). The example workflow
needed an `effect` dimension on the proposal (e.g.
`effect=edit_candidate`). We encoded it as a
`Fact(subject="proposal", field="effect")`. This works because the verifier
grounds `proposal.*` keys regardless of source — but it splits
proposal-shaped data across two channels, half struct, half fact list.

**Question.** Should `Proposal` grow extension fields (or a `dimensions`
map), or should all proposal-shaped data except action/actor/target live
in facts?

**Status.** Open. Do not act yet — single workflow signal. Re-evaluate
after workflows 2–4.

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
