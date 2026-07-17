# Gap: fail-logical adjudication

**Status:** named surface. Adjudication doctrine in force today.
Construction of the query surface forcing-case-gated.

Like the [typed-input provenance gap](./VERIFIER_TYPED_INPUT_PROVENANCE_GAP.md),
this is not a "candidate / non-binding" hedge. The surface is named
because retrofit cost is predictably high: the result vocabulary and
the solver-receipt fields are wire format, and the intended callers
(AG, Nightshift) will grow fallback adjudication paths whether or not
this contract exists. If they grow them without it, each caller embeds
its own solver and the custody boundary is gone before it was ever
drawn.

> *If you wait too long to name a surface, implementation will name it
> badly for you.*

## The third mode

Two failure policies are standard:

- **Fail open** — absence of proof does not block action.
- **Fail closed** — absence of proof blocks action.

This surface names a third:

- **Fail logical** — when the ordinary decision path is incomplete,
  reduce the admissibility question to a **bounded formal obligation**
  and let the verifier decide whether the requested transition follows
  from admitted facts and approved constraints.

The sharp distinction:

> **Fail-closed governs uncertainty about the world.
> Fail-logical governs incompleteness in the rule path.**

The solver must never decide whether a certificate is really valid or
a machine is actually healthy — that is world-uncertainty, and it
stays fail-closed. The solver may decide whether, *given admitted
facts*, the requested authority follows without contradiction — that
is rule-path incompleteness, and it is a satisfiability question.

Fail-logical is **not a fallback policy**. It is a **fallback
adjudication path whose own failure remains closed**: `UNKNOWN`,
timeout, unsupported theory, or a malformed obligation all refuse.
Only a decided result (a model, or a refutation with names attached)
is a decision.

## The escalation ladder

```text
policy decision  →  bounded logical adjudication  →  human judgment
```

- **Policy decision:** a direct, explicit rule answers. (Today's
  admissibility surface.)
- **Logical decision:** no direct rule, but the answer is *derivable*
  from admitted facts and approved constraints. (This surface.)
- **Discretionary decision:** the obligation itself cannot be formed
  without adding a premise — new judgment, new evidence, or new
  policy. Wake the human.

This fills the gap between "policy already knows" and "page someone at
03:17 because two predicates disagree." It is also the credible path
to **human-before-the-loop**: humans define the admissible world and
the escalation boundary; the system handles the combinatorics inside
it. "Human required" comes to mean *the machine reached the edge of
the model*, not *the code lacked a branch*.

## Custody boundary (doctrine — applies now)

1. **Callers construct closed decision problems; the verifier owns the
   proof machinery.** AG / Nightshift build a typed obligation from
   admitted facts; the verifier checks the encoding is within an
   approved theory profile, runs the solver, and returns a receipt.
   An engine embedding Z3 directly is the anti-pattern: the
   constitutional court acquiring tanks. One proof authority,
   portable receipts, replayable adjudications.
2. **Cooked, not fetched.** Unchanged from the provenance contract:
   an obligation is still `proposal + facts + rules`-shaped input.
   The verifier does not fetch truth on the hot path.
3. **No solver-authored facts.** The solver may derive consequences;
   it may never invent premises. Model values are *witness evidence*
   for a decided result, never new facts for a subsequent one.
4. **Typed, canonicalized obligations only.** No raw policy text to
   SMT. This composes with the global stochastic-boundary discipline:
   a stochastic subsystem terminates in a typed candidate artifact;
   downstream of the artifact everything is deterministic. The
   obligation is such an artifact.
5. **No unbounded optimization masquerading as authorization.** If an
   objective ever enters (least authority, least disturbance), it is
   lexicographic over a *declared, bounded* preference order inside an
   already-admissible envelope — never an open-ended "best action"
   search.
6. **UNKNOWN is refusal.** Timeout is refusal. Unsupported theory is
   refusal. Already enforced in code on the existing surface:
   `_check_rule` treats anything but `sat` as unsatisfied
   (`verifier.py`), pinned by
   `tests/test_invariants.py::test_solver_unknown_cannot_produce_allowed`.
7. **Refusal must be attributable.** A logical refusal names the
   constraints that cannot jointly hold (unsat core with rule
   identifiers), the way today's denials name every failing rule.
8. **The receipt carries the machinery.** Theory profile, timeout,
   seed, solver version, encoding digest. Replaying the same
   obligation and evidence yields the same adjudication class.

### Reconciling cores with "report all failing rules"

Existing doctrine says: never minimize unsat cores; governance must
see every violation. That rule governs **admissibility checking**,
where the question is "which rules does this proposal violate?" and
each rule is checked independently precisely so no violation hides
behind another.

An **entailment refusal** answers a different question: "why does no
model exist?" There, the named conflict set *is* the explanation, and
a core is the honest answer, not a minimized confession. The two
disciplines do not conflict; they belong to different query classes.
Do not import core-minimization back into admissibility checking, and
do not read "report everything" as forbidding cores on the
adjudication surface.

## Result vocabulary (named design)

The verifier never emits `authorized`-family words — that register
belongs to upstream authority kernels. Verifier-side classes stay in
the admissibility register:

| Verifier-side | Meaning | Caller-side reading (AG / Nightshift) |
|---|---|---|
| *(existing triad)* `allowed` | a direct rule path answered | `DirectlyAuthorized` |
| `entailed` | no direct rule, but the transition follows from admitted facts + approved constraints; model witness attached | `LogicallyAuthorized` |
| `refuted` | the transition cannot hold; named conflict set attached | `LogicallyRefused` |
| `indeterminate` | machinery failure or bounded incompleteness: UNKNOWN, timeout, unsupported theory | `Indeterminate` — refusal, pages as machinery |
| *(existing)* `invalid_input` | the obligation could not be formed: malformed, contradictory, or premise-incomplete input | `RequiresJudgment` — refusal, pages as judgment |

`indeterminate` and `RequiresJudgment` are operationally different
refusals and must page differently: the first means *the machinery
could not decide a well-formed question*; the second means *the
question cannot be formed without a new premise* — only the second
necessarily needs a human.

Only `entailed` and `refuted` are decisions. Everything else fails
closed.

W5 friction datum on this table: receipt-coexistence questions today
surface as `invalid_input` (transport register). Right machinery,
wrong register for adjudication use — a consistency query wants a
first-class `refuted` with the conflicting sources named. See
`tests/test_synthetic.py::test_nightshift_conflicting_receipts_are_transport_not_verdict`.

## Query classes (named design, not built)

1. **Entailment.** Given admitted facts and approved constraints, does
   the requested transition follow? ("Does staged authority entail the
   requested next step?")
2. **Consistency / coexistence.** Can two receipts, grants, or
   declared states jointly hold? Refusal names the conflict.
3. **Bounded plan existence.** Does any admissible action sequence
   reach the declared state — `∃ plan. reachable ∧ preserves(invariants)
   ∧ within(authority) ∧ within(budget)`? Refusal distinguishes
   "conflicting evidence" from "no consistent plan," with a core.
4. **Least-authority selection.** Lexicographic choice inside the
   admissible envelope: least authority, least irreversible effect,
   least disturbance, shortest path. **The most dangerous of the
   four** — see wall 5. Gate it hardest; build it last, if ever.

What the solver can resolve: composition, compatibility, entailment,
bounded choice. What it cannot: decide what matters, admit a new
fact, reinterpret an ambiguous incident, manufacture an exception.

## W5 findings (wind tunnel, 2026-07-16)

Synthetic Workflow 5 (`tests/fixtures/synthetic/nightshift_recovery/`,
friction notes in `tests/test_synthetic.py`) posed the entailment
question to the *current* IR. Findings:

- **The entailment already happens — outside the verifier.** "Does the
  grant cover this restart?" enters as an adapter-precomputed boolean
  fact. The verifier checks the result; the derivation has no receipt.
  The gap this document names, visible in a fixture.
- **C-2, third sighting.** Grant-covers-action is scope inclusion the
  IR cannot express. W1 per-grant literals, W4 interval booleans, W5
  entailment booleans — three shapes of one absence. The C-2 lean
  ("resist variable binding") holds for the admissibility surface;
  the pressure may resolve into this separate query class instead.
- **Plan existence and least-authority cannot even be posed** in the
  IR — no transitions, no effects, no objectives. Evidence that
  fail-logical is a different query class, not a stretch of this one.
- **Positive:** declare-before-disturb composes as one fact + one
  attribute + one rule; a heuristic detector's recommendation lands
  as an advisory basis — heard, not authority — instantiating the
  stochastic-boundary discipline in the existing IR.

## Lean note (downstream, not gating)

Lean's role, if it ever engages here, is the **envelope
meta-contract**, never the instance proofs:

- which facts may enter a solver obligation,
- which result classes can support authority (`entailed`, and nothing
  else on the positive side),
- that `UNKNOWN` / timeout / malformed evidence / unsupported theory
  cannot widen authority,
- that solver-derived permission is bounded by the original grant,
- that replaying the same obligation and evidence yields the same
  adjudication class.

Z3 handles the instance. Lean establishes that the court cannot annex
Poland.

## Build triggers (construction gate, narrow)

Any one of these concretizes the implementation:

- An actual AG or Nightshift consumer has a concrete ops decision that
  the direct rule path cannot answer and a bounded obligation can —
  and is prepared to construct the typed obligation.
- A workflow surfaces a question the admissibility surface cannot
  express (W5 already banked three: derivation receipts, coexistence
  register, plan existence) **and** a caller needs the answer, not
  just the observation.
- A caller starts embedding its own solver — the custody boundary is
  being eroded from outside; build the sanctioned path before the
  unsanctioned one calcifies.

When a trigger fires, the wind-tunnel methodology applies: synthetic
workflows of varied temperature against the *proposed obligation
shape* before any schema lands. W5 was the first; it scoped the gap,
it did not license construction.

## Composes with

- [VERIFIER_TYPED_INPUT_PROVENANCE_GAP.md](./VERIFIER_TYPED_INPUT_PROVENANCE_GAP.md)
  — obligations ride the same typed-input seam; provenance walls
  apply unchanged. A fail-logical receipt consumed downstream is a
  `Fact` like any other verdict: evidence, not authority.
- CLAUDE.md invariants — closed-world, scoped `claim_state` pre-gate,
  and the C-1 channel separation all apply to obligation inputs.
- Global stochastic-boundary discipline — the obligation is the typed
  artifact at which any stochastic caller terminates.
- skunkworks `patterns/fail-logical.md` — the constellation-level
  pattern statement; this document is the custody home for the
  contract.

## Keeper

> *The solver may derive consequences; it may never invent premises.
> Its strongest legal act is UNSAT with names attached.*

The point is not making the caller virtuous. It is making it
jurisdictionally small: the strongest thing a confused or ambitious
caller can legally obtain from this surface is a refusal that
explains itself.
