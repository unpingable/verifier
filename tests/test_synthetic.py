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
