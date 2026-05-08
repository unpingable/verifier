"""Proposal.attributes — domain-specific extension data.

Schema 0.3.0 introduced `Proposal.attributes: dict[str, str | int | bool]`
so that proposal-shaped extension data (effect, duration, version, reason,
…) doesn't have to masquerade as `Fact(subject="proposal", field=...)`.

This file tests the attribute-to-rule pipeline directly, without the
narrative weight of the synthetic workflows:

- Attribute keys appear in the grounded set under (proposal, key).
- Rule atoms with subject="proposal" can reference attributes.
- Values normalize correctly through the solver (str/int/bool).
- Multiple attributes coexist.
- Missing attribute keys fail closed-world like any other ungrounded
  (subject, field) pair.

The boundary the schema preserves:
- Proposal core (action/actor/target/scope) is the audit spine.
- Proposal.attributes is *proposed intent* (domain-specific shape).
- Fact is *external evidence*.
"""

from __future__ import annotations

from models import ConstraintAtom, ConstraintRule, Fact, Proposal
from verifier import verify


PROPOSAL_BASE = {"action": "promote", "actor": "operator", "target": "doc", "scope": "ops"}


def _rule(rule_id: str, atoms: list[ConstraintAtom]) -> ConstraintRule:
    return ConstraintRule(
        rule_id=rule_id,
        description="attribute test rule",
        kind="constraint",
        require=atoms,
    )


def test_string_attribute_grounds_and_satisfies():
    proposal = Proposal(**PROPOSAL_BASE, attributes={"effect": "advisory"})
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="effect", op="eq", value="advisory")
    ])
    verdict = verify(proposal, facts=[], rules=[rule])
    assert verdict.status == "allowed"


def test_int_attribute_normalizes_to_string():
    """Attribute values are normalized the same way Fact values are
    (booleans → 'true'/'false', ints → str(int)).  Compare against the
    string form of the literal in the rule."""
    proposal = Proposal(**PROPOSAL_BASE, attributes={"duration_hours": 6})
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="duration_hours", op="eq", value=6)
    ])
    verdict = verify(proposal, facts=[], rules=[rule])
    assert verdict.status == "allowed"


def test_bool_attribute_normalizes():
    proposal = Proposal(**PROPOSAL_BASE, attributes={"approved": True})
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="approved", op="eq", value=True)
    ])
    verdict = verify(proposal, facts=[], rules=[rule])
    assert verdict.status == "allowed"


def test_attribute_value_mismatch_denies():
    """Attribute is grounded with a different value than the rule
    requires — evidence-against, denial via failed_rules."""
    proposal = Proposal(**PROPOSAL_BASE, attributes={"effect": "durable"})
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="effect", op="eq", value="advisory")
    ])
    verdict = verify(proposal, facts=[], rules=[rule])
    assert verdict.status == "denied"
    assert "r1" in {r.rule_id for r in verdict.failed_rules}


def test_missing_attribute_fails_closed_world():
    """Attribute key not in the dict → not grounded → closed-world denial.
    Same semantics as a missing fact."""
    proposal = Proposal(**PROPOSAL_BASE, attributes={})
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="effect", op="eq", value="advisory")
    ])
    verdict = verify(proposal, facts=[], rules=[rule])
    assert verdict.status == "denied"
    missing_pairs = {(m.subject, m.field) for m in verdict.missing_facts}
    assert ("proposal", "effect") in missing_pairs


def test_multiple_attributes_coexist():
    proposal = Proposal(**PROPOSAL_BASE, attributes={
        "effect": "durable",
        "version": "0.3.0",
        "duration_hours": 6,
        "approved": True,
    })
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="effect", op="eq", value="durable"),
        ConstraintAtom(subject="proposal", field="version", op="eq", value="0.3.0"),
        ConstraintAtom(subject="proposal", field="duration_hours", op="eq", value=6),
        ConstraintAtom(subject="proposal", field="approved", op="eq", value=True),
    ])
    verdict = verify(proposal, facts=[], rules=[rule])
    assert verdict.status == "allowed"


def test_attributes_do_not_appear_in_used_facts():
    """`used_facts` is the channel for *external evidence*.  Attributes
    are *proposed intent* and live on the proposal envelope, not in
    facts.  This separation must hold post-C-1."""
    proposal = Proposal(**PROPOSAL_BASE, attributes={"effect": "durable"})
    fact = Fact(subject="actor", field="role", value="ops", source="hr")
    rule = _rule("r1", [
        ConstraintAtom(subject="proposal", field="effect", op="eq", value="durable")
    ])
    verdict = verify(proposal, facts=[fact], rules=[rule])

    assert verdict.status == "allowed"
    # Only the actual fact appears; attribute values never become facts.
    assert len(verdict.used_facts) == 1
    assert verdict.used_facts[0].source == "hr"
    assert all(f.subject != "proposal" for f in verdict.used_facts)


def test_attribute_in_when_clause_fires_rule():
    """Attributes are accessible from rule when-clauses too — not just
    require-clauses.  This matters for advisory basis machinery, which
    keys off whether a rule fires."""
    proposal = Proposal(**PROPOSAL_BASE, attributes={"effect": "advisory"})
    rule = ConstraintRule(
        rule_id="basis.advisory_only",
        description="advisory basis fires when proposal asks for advisory",
        kind="basis",
        basis_effect="advisory",
        when=[ConstraintAtom(subject="proposal", field="effect", op="eq", value="advisory")],
        require=[ConstraintAtom(subject="actor", field="trusted", op="eq", value="true")],
    )
    facts = [Fact(subject="actor", field="trusted", value="true", source="hr")]
    verdict = verify(proposal, facts=facts, rules=[rule])

    # Advisory basis fired and held; no actionable basis present.
    assert verdict.status == "advisory"
