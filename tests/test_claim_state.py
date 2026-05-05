"""claim_state pre-gate: scoped exclusion of non-current evidence.

A fact carries a `claim_state` lifecycle stamp (current | stale |
revoked | expired).  Non-current facts are excluded from the solver
pass — they cannot ground a rule, prove a basis, or contradict a
current fact.  Closed-world fall-through handles the rest.

The pre-gate is **scoped**, not global:
- A non-current fact whose (subject, field) is referenced by a rule
  produces a StaleFact diagnostic so the consumer knows their input
  contained aged-out evidence in scope.
- A non-current fact unrelated to any rule produces no diagnostic and
  no denial.  Stale noise is not a verdict.

This ports the Lean kernel's stale-basis invariant
("stale/revoked/expired claim cannot produce Authorized") without
importing the rest of the courthouse.
"""

from __future__ import annotations

import pytest

from models import ConstraintAtom, ConstraintRule, Fact, Proposal
from verifier import verify


PROPOSAL = Proposal(action="deploy", actor="worker-a", target="service/api", scope="prod")


def _scope_rule() -> ConstraintRule:
    return ConstraintRule(
        rule_id="standing.scope_match",
        description="Granted scope must match",
        kind="standing",
        require=[ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod")],
    )


# ------------------------------------------------------------------
# Default behavior preserved
# ------------------------------------------------------------------

def test_default_claim_state_is_current():
    """Existing payloads with no claim_state field continue to evaluate
    exactly as before.  This is the backward-compat invariant."""
    f = Fact(subject="actor", field="granted_scope", value="prod", source="test")
    assert f.claim_state == "current"


# ------------------------------------------------------------------
# Stale facts are filtered from evaluation
# ------------------------------------------------------------------

@pytest.mark.parametrize("state", ["stale", "revoked", "expired"])
def test_non_current_fact_is_excluded_from_evaluation(state):
    """A stale/revoked/expired fact does not ground its (subject, field)
    for the solver.  The rule that needed it falls through to closed-world
    denial."""
    facts = [Fact(
        subject="actor", field="granted_scope", value="prod",
        source="standing:expired", claim_state=state,
    )]
    verdict = verify(PROPOSAL, facts=facts, rules=[_scope_rule()])

    assert verdict.status == "denied"
    assert verdict.failed_rules[0].rule_id == "standing.scope_match"


@pytest.mark.parametrize("state", ["stale", "revoked", "expired"])
def test_non_current_fact_referenced_by_rule_surfaces_diagnostic(state):
    """The consumer needs to know the closed-world denial wasn't 'I had no
    evidence'; it was 'I had aged-out evidence and dropped it'."""
    facts = [Fact(
        subject="actor", field="granted_scope", value="prod",
        source="standing:expired-101", claim_state=state,
    )]
    verdict = verify(PROPOSAL, facts=facts, rules=[_scope_rule()])

    assert len(verdict.stale_facts) == 1
    sf = verdict.stale_facts[0]
    assert sf.rule_id == "standing.scope_match"
    assert sf.subject == "actor"
    assert sf.field == "granted_scope"
    assert sf.source == "standing:expired-101"
    assert sf.claim_state == state


def test_non_current_fact_excluded_from_used_facts():
    """used_facts reflects what the verifier actually consulted, not what
    was submitted.  Stale facts are surfaced via stale_facts instead."""
    facts = [
        Fact(subject="actor", field="granted_scope", value="prod",
             source="active", claim_state="current"),
        Fact(subject="actor", field="granted_scope", value="prod",
             source="old", claim_state="expired"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=[_scope_rule()])

    assert len(verdict.used_facts) == 1
    assert verdict.used_facts[0].source == "active"


# ------------------------------------------------------------------
# Scoping: no global stale-scanning
# ------------------------------------------------------------------

def test_unreferenced_stale_fact_is_silent():
    """A stale fact whose (subject, field) appears in NO rule is irrelevant
    noise.  No diagnostic, no denial.  This is the no-spooky-action
    invariant chatty hammered."""
    facts = [
        # Current fact that satisfies the only rule
        Fact(subject="actor", field="granted_scope", value="prod", source="active"),
        # Stale fact unrelated to any rule
        Fact(subject="weather", field="forecast", value="rain",
             source="weather:old", claim_state="stale"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=[_scope_rule()])

    assert verdict.status == "allowed"
    assert verdict.stale_facts == []


def test_stale_fact_referenced_only_in_when_clause_still_surfaces():
    """A stale fact in a rule's when-clause prevents the rule from firing
    (closed-world).  Still surface the diagnostic so the consumer knows
    why the rule didn't engage."""
    rule = ConstraintRule(
        rule_id="constraint.conditional",
        description="only applies when target is in maintenance",
        kind="constraint",
        when=[ConstraintAtom(subject="target", field="maintenance_window", op="eq", value="true")],
        require=[ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod")],
    )
    facts = [
        Fact(subject="target", field="maintenance_window", value="true",
             source="schedule:old", claim_state="expired"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=[rule])

    assert any(sf.field == "maintenance_window" for sf in verdict.stale_facts)


# ------------------------------------------------------------------
# Interaction with other features
# ------------------------------------------------------------------

def test_stale_fact_does_not_cause_invalid_input_with_current_disagreement():
    """A stale fact that disagrees with a current fact is not a contradiction.
    The stale one is filtered before consistency check; the current one wins
    cleanly."""
    facts = [
        Fact(subject="actor", field="granted_scope", value="prod",
             source="active", claim_state="current"),
        Fact(subject="actor", field="granted_scope", value="staging",
             source="old", claim_state="revoked"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=[_scope_rule()])

    assert verdict.status == "allowed"
    assert verdict.contradictions == []


def test_stale_basis_cannot_produce_allowed():
    """The Lean invariant: stale/revoked/expired evidence cannot produce
    an authorized verdict.  An actionable basis depending only on stale
    evidence falls through to denied."""
    basis = ConstraintRule(
        rule_id="basis.standing",
        description="standing-based basis",
        kind="basis",
        basis_effect="actionable",
        require=[ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod")],
    )
    facts = [Fact(
        subject="actor", field="granted_scope", value="prod",
        source="standing:revoked", claim_state="revoked",
    )]
    verdict = verify(PROPOSAL, facts=facts, rules=[basis])

    assert verdict.status == "denied"
    assert any(sf.rule_id == "basis.standing" for sf in verdict.stale_facts)
