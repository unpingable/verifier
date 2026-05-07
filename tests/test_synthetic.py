"""Synthetic workflow fixtures — wind tunnel for the verifier.

The point of these is **not** to prove the README.  It's to find out
whether the IR (proposal + facts + rules + verdict) survives translation
from naturally-shaped domain vocabularies.

> A synthetic workflow is successful when it makes the adapter sweat,
> not when it makes the verifier look smart.

Each workflow lives under tests/fixtures/synthetic/<name>/ as one or
more pure JSON payloads (no metadata smuggled in — what the verifier
sees is what's on disk).  Expected verdicts are encoded in this test
file, not in the fixtures, so the fixtures stay pure and reusable.

Friction observed during translation is recorded in the docstring of
each workflow's section below.  Friction is data — when the same
friction shows up across three workflows, that's a signal.  When it
shows up in one and one only, it's a local quirk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import run_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "synthetic"


def _load(rel: str) -> dict:
    return json.loads((FIXTURES / rel).read_text(encoding="utf-8"))


# ==================================================================
# Workflow 1: Standing grant check
# ==================================================================
#
# Domain: a Standing grant authorizes a principal to perform a bounded
# set of actions within a bounded scope, with a recorded lifecycle
# (current / expired / revoked / stale).  The verifier is asked
# whether a given proposal falls inside the grant.
#
# Adapter sweat — what didn't translate cleanly:
#
# 1. Proposal struct shape.  Chatty's example proposal has
#    {action, actor, target, effect}.  Our Proposal is fixed at
#    {action, actor, target, scope}.  Compromise: encode `effect` as a
#    Fact with subject="proposal".  This works because the verifier
#    grounds proposal.* keys regardless of where they came from, but
#    it duplicates the "this is part of the proposal" channel: half in
#    the struct, half in the fact list.  Forces the question of
#    whether Proposal should grow extension fields, or whether all of
#    its dimensions should be facts.  Note, do not act on it yet.
#
# 2. Per-grant rule literals.  Atoms compare a (subject, field) to a
#    literal; they cannot compare two atoms.  So rules cannot
#    parametrically say "proposal.scope must equal actor.granted_scope"
#    — they must encode the literal value of the grant, e.g.
#    "proposal.scope == 'agent_gov/docs' AND actor.granted_scope ==
#    'agent_gov/docs'".  That means each grant compiles to its own
#    per-grant rule.  This is OK at small scale and probably fine
#    forever, but flag it: the IR has no unification / variable
#    binding, by design.
#
# 3. Naming overlap on `scope`.  Proposal.scope is "what scope is
#    this action operating in".  The existing Standing adapter uses
#    `granted_scope` to mean "what action is granted" (i.e., its scope
#    crate's `scope.action` field).  These are different things wearing
#    the same word.  In this synthetic we use scope=path-subset and
#    encode action-class as `granted_effect` separately.  The friction
#    is in the upstream domain's vocabulary, not in our IR — but it
#    will recur.
#
# 4. claim_state pre-gate fits the grant lifecycle perfectly.  No
#    sweat here — the expired-grant case maps directly onto
#    claim_state="expired" on the grant facts, and the verifier's
#    scoped pre-gate produces the right verdict (denied) and the right
#    diagnostic (stale_facts populated for the standing rules).

STANDING_GRANT_CASES = [
    ("standing_grant_check/allowed_edit_candidate.json", "allowed"),
    ("standing_grant_check/denied_policy_mutation.json", "denied"),
    ("standing_grant_check/denied_expired_grant.json",   "denied"),
    ("standing_grant_check/advisory_non_actionable.json", "advisory"),
]


@pytest.mark.parametrize("fixture,expected", STANDING_GRANT_CASES)
def test_standing_grant_workflow(fixture, expected):
    verdict = run_payload(_load(fixture))
    assert verdict.status == expected, (
        f"{fixture}: expected {expected}, got {verdict.status}"
    )


def test_standing_grant_expired_surfaces_stale_facts():
    """Expired grant facts should show up as stale_facts diagnostics
    on the rules that referenced them.  This is the consumer's
    breadcrumb: 'closed-world denial happened because evidence aged out',
    not 'I had no evidence at all'."""
    verdict = run_payload(_load("standing_grant_check/denied_expired_grant.json"))

    assert verdict.stale_facts, "expired grant should surface stale_facts"
    sources = {sf.source for sf in verdict.stale_facts}
    assert "standing:grant-123" in sources

    # All three grant facts (principal_id, granted_scope, granted_effect)
    # should appear as stale, attributed to one or more standing rules.
    stale_fields = {sf.field for sf in verdict.stale_facts}
    assert {"principal_id", "granted_scope", "granted_effect"} <= stale_fields


def test_standing_grant_dimension_projection():
    """The denied case should produce dimension diagnostics that say
    standing failed, not just 'something failed'.  This is the value of
    rule kinds — the consumer gets to ask 'which dimension said no'
    without hand-correlating rule_ids."""
    verdict = run_payload(_load("standing_grant_check/denied_policy_mutation.json"))

    assert "standing" in verdict.dimension_verdicts
    assert verdict.dimension_verdicts["standing"].status == "failed"

    # The basis rule also fails (its require references edit_candidate),
    # so the basis dimension should report failure too.
    assert "basis" in verdict.dimension_verdicts
    assert verdict.dimension_verdicts["basis"].status == "failed"


def test_standing_grant_advisory_does_not_fail_anything():
    """Advisory case: no rule failed, but verdict is 'advisory'.  This
    is the only path in the system where the verdict is non-allowed
    despite zero failures — it's the basis_effect machinery, not a
    failure-counting machinery."""
    verdict = run_payload(_load("standing_grant_check/advisory_non_actionable.json"))

    assert verdict.status == "advisory"
    assert verdict.failed_rules == []
    assert verdict.warnings == []


# ==================================================================
# Workflow 2: Release / merge gate
# ==================================================================
#
# Domain: a CI pipeline asks whether a repo is eligible to be tagged.
# Pure deny-rule constraint check: tests pass, cross-surface parity
# holds, README current, working tree clean.  No basis dimension at all.
# This is intentionally mundane — chatty's framing was "a nice antidote
# to formal methods as ceremonial robe."
#
# Adapter sweat — what didn't translate cleanly:
#
# 1. Proposal struct shape, again (stronger signal for C-1).  Chatty's
#    example had {action, repo, version}; Standing's had
#    {action, actor, target, effect}; ours is fixed at
#    {action, actor, target, scope}.  Each domain wants different
#    fields.  Here we mapped repo→target and version→scope, which
#    *works* but stretches the words "target" and "scope" past the
#    point where they pull their weight.  This is now two workflows
#    pointing at the same friction.
#
# 2. The actor is invented.  Chatty's release proposal had no actor —
#    "tag a release" is more of an event than a directed action.  Our
#    Proposal.actor is required (min_length=1), so we put
#    "release-pipeline" in.  This is real friction: not every
#    admissibility check has a meaningful actor.  Recorded as C-5.
#
# 3. Verdict triad fall-through works.  No basis rules submitted →
#    `_aggregate_status` takes the "no basis dimension in play" branch
#    and returns "allowed" when no deny rules fail.  Pure constraint
#    workflows do not feel forced to have a basis.  Positive signal.
#
# 4. Subjects expanded naturally.  We used subject ∈ {tests, parity,
#    readme, git} for these facts, which goes beyond the
#    actor/target/proposal trio that the existing tests use.  The
#    schema already permits this — `subject` is a non-empty string —
#    but the docstring example list ("actor", "target", "proposal",
#    "system", "policy") may want extending to acknowledge that
#    subjects are an open vocabulary.  Minor.

RELEASE_GATE_CASES = [
    ("release_merge_gate/allowed_clean_release.json",       "allowed"),
    ("release_merge_gate/denied_failing_tests.json",        "denied"),
    ("release_merge_gate/denied_dirty_tree.json",           "denied"),
    ("release_merge_gate/denied_multiple_gates_fail.json",  "denied"),
]


@pytest.mark.parametrize("fixture,expected", RELEASE_GATE_CASES)
def test_release_gate_workflow(fixture, expected):
    verdict = run_payload(_load(fixture))
    assert verdict.status == expected, (
        f"{fixture}: expected {expected}, got {verdict.status}"
    )


def test_release_gate_no_basis_rules_falls_through_to_allowed():
    """When all four constraint rules pass and there are no basis rules
    in the input, the verdict is 'allowed' via the fall-through branch
    of _aggregate_status.  This pins the legacy-compat path: pure
    constraint workflows do not need to invent a basis."""
    verdict = run_payload(_load("release_merge_gate/allowed_clean_release.json"))

    assert verdict.status == "allowed"
    # No basis rules submitted, so basis dimension does not appear.
    assert "basis" not in verdict.dimension_verdicts
    # Constraint dimension passed cleanly.
    assert verdict.dimension_verdicts["constraint"].status == "passed"


def test_release_gate_multiple_failures_all_reported():
    """Two gates fail (tests + parity) plus the dirty tree.  All three
    should appear in failed_rules — the verifier reports every failing
    rule, not a minimal subset.  This is the design property that lets
    the consumer see the full picture in one round-trip."""
    verdict = run_payload(_load("release_merge_gate/denied_multiple_gates_fail.json"))

    assert verdict.status == "denied"
    failed_ids = {r.rule_id for r in verdict.failed_rules}
    assert "release.tests_pass" in failed_ids
    assert "release.cross_surface_parity" in failed_ids
    assert "release.clean_tree" in failed_ids
    # readme.current = true, so that rule should NOT be in failed_rules.
    assert "release.readme_current" not in failed_ids


def test_release_gate_dimension_says_failed_not_missing():
    """Failure mode here is evidence-against (tests.pass=false, not
    absent), so the constraint dimension should report 'failed' rather
    than 'missing'.  This validates that the missing-vs-failed
    distinction in DimensionVerdict actually means what it says."""
    verdict = run_payload(_load("release_merge_gate/denied_failing_tests.json"))

    dv = verdict.dimension_verdicts["constraint"]
    assert dv.status == "failed", (
        f"expected 'failed' (evidence against tests.pass), got {dv.status!r}"
    )


# ==================================================================
# Workflow 3: LLM claim promotion
# ==================================================================
#
# Domain: an operator proposes turning an LLM-generated claim into
# something durable — repo doctrine, README claim, architecture note.
# This is the spicy synthetic, the one that directly models the thing
# everyone else is moralizing about: when does fluent output get to count?
#
# The shape of the answer the verifier should produce:
# - Allowed only when an actionable basis exists (e.g., independent
#   human review with receipt).
# - Advisory when the only basis is an LLM session AND the proposal
#   itself is for an advisory effect (you can hear it; you cannot
#   ratify it as durable).
# - Denied when the proposal asks for durable but the basis is LLM
#   (Rule A — explicit policy that LLM source cannot bridge to durable),
#   or when the proposal is durable but lacks independent receipt
#   (Rule B — durable requires receipt regardless of source).
#
# Adapter sweat — what didn't translate cleanly:
#
# 1. Effect-on-proposal again, third signal for C-1.  Same friction as
#    Standing (effect=edit_candidate) and Release (repo+version).  This
#    domain wants `effect=durable_doctrine` or `effect=advisory_note`.
#    Encoded as a Fact, third time in a row.  C-1 is now a hard signal,
#    not a quirk.
#
# 2. Multi-role actor (C-5 enrichment).  Roles in this domain:
#    - claimant: who originated the claim (in claim.source)
#    - proposer: who's asking to promote (in Proposal.actor)
#    - authority: who can ratify (implicit in the basis rules)
#    - publisher: where the claim lands (in Proposal.target)
#    Our schema collapses some of these into one field.  We use
#    Proposal.actor=proposer and put the rest as facts on claim.* —
#    works, but reinforces the user's directional lean: actor really
#    means "accountable initiator," and the field name is too narrow.
#
# 3. The "actor IS source" case.  In denied_llm_durable_with_receipt
#    we set actor="claude-opus-4.7" — the model proposing to promote
#    its own claim into durable doctrine.  We have no rule that detects
#    this self-promotion pattern; expressing "actor MUST NOT equal
#    claim.source" requires atom-pair comparison, which the IR does not
#    support (C-2 again).  The verdict in that case is still denied,
#    but for the right reason (LLM source) rather than the spicier
#    reason (self-promotion).  Recording, not acting.
#
# 4. Verdict triad is doing exactly what it was designed to do.  The
#    advisory case (Rule C fires alone, no actionable basis) produces
#    status="advisory" with zero rule failures.  This is the
#    "heard, not authorized" channel that motivated chatty's design
#    in the first place.  Strong positive signal: the schema was
#    built for this, and this is what it looks like in use.
#
# 5. The "receipt does not bridge sources" property emerges naturally.
#    Case 4 (denied_llm_durable_with_receipt) has independent_receipt
#    AND attempts durable AND has LLM source.  Rule B (receipt
#    requirement) passes; Rule A (no LLM-to-durable) still fails.  The
#    verdict is denied for the right reason.  This is the verifier
#    proving that "receipt is necessary but not sufficient" can be
#    expressed cleanly — orthogonal rules compose into a tight gate.

LLM_CLAIM_CASES = [
    ("llm_claim_promotion/allowed_durable_with_human_review.json", "allowed"),
    ("llm_claim_promotion/advisory_llm_advisory_note.json",        "advisory"),
    ("llm_claim_promotion/denied_llm_attempts_durable.json",       "denied"),
    ("llm_claim_promotion/denied_llm_durable_with_receipt.json",   "denied"),
]


@pytest.mark.parametrize("fixture,expected", LLM_CLAIM_CASES)
def test_llm_claim_workflow(fixture, expected):
    verdict = run_payload(_load(fixture))
    assert verdict.status == expected, (
        f"{fixture}: expected {expected}, got {verdict.status}"
    )


def test_llm_claim_advisory_is_basis_level_not_severity_level():
    """The advisory verdict comes from basis_effect=advisory on a basis
    rule firing — NOT from any rule having severity=warn.  This pins the
    distinction chatty hammered: warning means 'this rule did not block,'
    advisory means 'this basis can be heard but cannot support action.'
    Different animals."""
    verdict = run_payload(_load("llm_claim_promotion/advisory_llm_advisory_note.json"))

    assert verdict.status == "advisory"
    assert verdict.failed_rules == []
    assert verdict.warnings == [], (
        "advisory should not be produced via warn-severity rules"
    )

    # The advisory came from the advisory-basis rule firing.  Verify by
    # checking the basis dimension passed (the advisory rule didn't
    # fail; it just doesn't grant action).
    assert verdict.dimension_verdicts["basis"].status == "passed"


def test_llm_claim_receipt_does_not_bridge_sources():
    """Even with independent_receipt=true, an LLM-source claim cannot
    promote to durable.  Rule A (LLM cannot support durable) does the
    work that Rule B (durable requires receipt) cannot — the two are
    orthogonal gates and both must pass.  This is the synthetic's
    sharpest test of compositional rule logic."""
    verdict = run_payload(
        _load("llm_claim_promotion/denied_llm_durable_with_receipt.json")
    )

    assert verdict.status == "denied"
    failed_ids = {r.rule_id for r in verdict.failed_rules}
    assert "claim.llm_cannot_support_durable" in failed_ids
    # Rule B (durable_requires_independent_receipt) should NOT fail —
    # the receipt is present.  The denial is about source, not receipt.
    assert "claim.durable_requires_independent_receipt" not in failed_ids


def test_llm_claim_human_review_unlocks_durable():
    """The mirror of the previous test: human_review source plus
    independent_receipt produces an actionable basis that supports
    durable doctrine.  Confirms the 'durable_doctrine is reachable'
    invariant — the verifier isn't refusing all durable promotions,
    only LLM-sourced ones."""
    verdict = run_payload(
        _load("llm_claim_promotion/allowed_durable_with_human_review.json")
    )

    assert verdict.status == "allowed"
    # The actionable basis fired and held.
    basis_dv = verdict.dimension_verdicts["basis"]
    assert basis_dv.status == "passed"


# ==================================================================
# Workflow 4: NQ alert suppression / maintenance gate
# ==================================================================
#
# Domain: an operator wants to suppress an active NQ finding during a
# maintenance window.  Pure constraint check (no basis dimension), but
# operationally rich: high-severity suppression requires window + ack +
# witness coverage + duration-within-window.  Each gate stems from a
# different system (calendar / nightshift / nq-witness / adapter).
#
# Operationally this is the keeper line for maintenance discipline:
# "maintenance is not incident resolution, and suppression is not
# disappearance."
#
# Adapter sweat — what didn't translate cleanly:
#
# 1. C-1 fourth signal.  Chatty's proposal had {action, finding,
#    duration, reason}.  We mapped finding→target, kept action, invented
#    actor=nightshift-operator, set scope="ops", and pushed both
#    duration_hours and reason into facts on subject="proposal".  Same
#    pattern as prior workflows.  Four workflows, same friction.
#
# 2. C-2 in a new shape: interval comparison.  The natural rule is
#    "suppression duration must not exceed maintenance window" — that
#    requires comparing two values (proposal.duration vs
#    window.duration), which the IR does not support.  Workaround: the
#    adapter pre-computes a boolean fact `proposal.duration_within_window`
#    and the rule checks that fact for equality with true.  Works, but
#    the adapter is doing arithmetic the verifier deliberately can't.
#    This is a different shape of C-2 friction than the per-grant rule
#    duplication seen in W1 — both are downstream consequences of "no
#    atom-pair comparison."
#
# 3. Multi-source provenance is doing real work (positive).  Facts here
#    come from nq, calendar, nightshift, nq-witness, adapter, and
#    proposal — six sources.  The verifier doesn't care; `source` is
#    free-form.  This is operationally honest: in the real world, an
#    admissibility check pulls from many systems, and the verifier's
#    job is to compose them, not to know them.
#
# 4. `op: in` over enumerated values is more readable than `op: neq`.
#    For the witness rule — "coverage must be in {complete, partial}" —
#    is clearer than "coverage must not equal cannot_testify".  The
#    `in` form scales as the witness vocabulary grows; `neq` would not.
#    Minor positive signal for the operator vocabulary.
#
# 5. Actor weirdness is *less* sweaty here than W3.  The accountable
#    initiator is clearly the operator triggering the suppression —
#    one role, no ambiguity.  This domain has a clean actor concept.
#    Different domains stretch C-5 differently; some don't stretch it
#    at all.

NQ_SUPPRESSION_CASES = [
    ("nq_suppression_gate/allowed_clean_suppression.json",      "allowed"),
    ("nq_suppression_gate/denied_no_maintenance_window.json",   "denied"),
    ("nq_suppression_gate/denied_witness_cannot_testify.json",  "denied"),
    ("nq_suppression_gate/denied_duration_exceeds_window.json", "denied"),
]


@pytest.mark.parametrize("fixture,expected", NQ_SUPPRESSION_CASES)
def test_nq_suppression_workflow(fixture, expected):
    verdict = run_payload(_load(fixture))
    assert verdict.status == expected, (
        f"{fixture}: expected {expected}, got {verdict.status}"
    )


def test_nq_suppression_witness_block_uses_in_operator():
    """The witness rule uses `op: in` over enumerated allowed values
    rather than `op: neq` against a forbidden one.  Verifies the verdict
    correctly attributes the failure to the witness rule when coverage
    is `cannot_testify`."""
    verdict = run_payload(_load("nq_suppression_gate/denied_witness_cannot_testify.json"))

    assert verdict.status == "denied"
    failed_ids = {r.rule_id for r in verdict.failed_rules}
    assert "nq.witness_coverage_must_allow" in failed_ids
    # Other rules should NOT fail — only witness is the problem here.
    assert failed_ids == {"nq.witness_coverage_must_allow"}


def test_nq_suppression_duration_uses_precomputed_fact():
    """Interval comparison (proposal.duration vs window.duration) is
    not expressible in the IR — the adapter must pre-compute a boolean
    fact `duration_within_window`.  The rule then checks that fact for
    eq=true.  This pins the C-2 workaround pattern: when the IR can't
    compare, the adapter does the math and exposes the result."""
    verdict = run_payload(_load("nq_suppression_gate/denied_duration_exceeds_window.json"))

    assert verdict.status == "denied"
    failed_ids = {r.rule_id for r in verdict.failed_rules}
    assert "nq.duration_within_window" in failed_ids
    # The duration_within_window fact is the pre-computed signal.
    duration_facts = [
        f for f in verdict.used_facts
        if f.field == "duration_within_window"
    ]
    assert len(duration_facts) == 1
    assert duration_facts[0].value is False


def test_nq_suppression_severity_gating_works():
    """Severity-conditional rules (when severity=high) fire on this
    high-severity finding.  In the no-window case, only the
    high-severity-requires-maintenance rule fails — confirming the
    when-clause is gating correctly and the rule is doing the
    severity-conditional work."""
    verdict = run_payload(_load("nq_suppression_gate/denied_no_maintenance_window.json"))

    assert verdict.status == "denied"
    failed_ids = {r.rule_id for r in verdict.failed_rules}
    assert "nq.high_severity_requires_maintenance" in failed_ids
    # Operator ack rule was satisfied (ack exists), so it should NOT
    # be in failed_rules.
    assert "nq.high_severity_requires_operator_ack" not in failed_ids


def test_nq_suppression_no_basis_falls_through_like_release_gate():
    """W4 is a pure constraint workflow — no basis rules submitted.
    The verdict mechanism falls through to allowed/denied via failure
    counting alone.  This is the same path as W2; together they prove
    pure constraint workflows are first-class, not second-class."""
    verdict = run_payload(_load("nq_suppression_gate/allowed_clean_suppression.json"))

    assert verdict.status == "allowed"
    # No basis dimension — basis isn't in the dimension_verdicts dict.
    assert "basis" not in verdict.dimension_verdicts
    assert verdict.dimension_verdicts["constraint"].status == "passed"
