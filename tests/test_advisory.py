"""Advisory basis semantics — the verdict trichotomy.

The verifier emits one of three admissibility verdicts:

    allowed  ⇐  some actionable basis fired and held
    advisory ⇐  only advisory bases fired (you can hear it; you cannot act on it)
    denied   ⇐  a deny-rule failed, OR basis rules were submitted but none fired

`invalid_input` is a schema/transport failure, not an admissibility verdict.
It does not appear in this file.

The keeper constraint, recorded explicitly:

    Verifier may classify admissibility.  It must not become the authority
    that spends it.

Advisory is basis-level (basis_effect), never repurposed `warn`.  A warning
is "this rule did not block the verdict."  An advisory basis is "this basis
can be heard but cannot support action."  Different animal.
"""

from __future__ import annotations

import pytest

from models import ConstraintAtom, ConstraintRule, Fact, Proposal
from verifier import verify


PROPOSAL = Proposal(action="deploy", actor="worker-a", target="service/api", scope="prod")


def _actionable_basis(rule_id: str, when_action: str = "deploy") -> ConstraintRule:
    return ConstraintRule(
        rule_id=rule_id,
        description="actionable basis",
        kind="basis",
        basis_effect="actionable",
        when=[ConstraintAtom(subject="proposal", field="action", op="eq", value=when_action)],
        require=[ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod")],
    )


def _advisory_basis(rule_id: str, when_action: str = "deploy") -> ConstraintRule:
    return ConstraintRule(
        rule_id=rule_id,
        description="advisory basis",
        kind="basis",
        basis_effect="advisory",
        when=[ConstraintAtom(subject="proposal", field="action", op="eq", value=when_action)],
        require=[ConstraintAtom(subject="target", field="prior_review", op="eq", value="true")],
    )


def test_actionable_basis_fires_and_holds_yields_allowed():
    facts = [Fact(subject="actor", field="granted_scope", value="prod", source="standing:1")]
    verdict = verify(PROPOSAL, facts=facts, rules=[_actionable_basis("basis.grant")])

    assert verdict.status == "allowed"


def test_only_advisory_basis_yields_advisory():
    """Advisory basis fired and held; no actionable basis present.
    Verdict must be 'advisory' — heard, but unsupported for action."""
    facts = [Fact(subject="target", field="prior_review", value="true", source="precedent:1")]
    verdict = verify(PROPOSAL, facts=facts, rules=[_advisory_basis("basis.precedent")])

    assert verdict.status == "advisory"


def test_actionable_takes_precedence_over_advisory():
    """When both actionable and advisory bases fire and hold, the
    presence of actionable authority pulls the verdict to 'allowed'.
    Advisory does not weaken an authorized verdict."""
    facts = [
        Fact(subject="actor", field="granted_scope", value="prod", source="standing:1"),
        Fact(subject="target", field="prior_review", value="true", source="precedent:1"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=[
        _actionable_basis("basis.grant"),
        _advisory_basis("basis.precedent"),
    ])

    assert verdict.status == "allowed"


def test_basis_rules_submitted_but_none_fire_yields_denied():
    """Both basis rules have when-clauses that don't match this proposal.
    No basis grants authority for this action → denied, even though no
    rule technically failed."""
    facts = [
        Fact(subject="actor", field="granted_scope", value="prod", source="standing:1"),
        Fact(subject="target", field="prior_review", value="true", source="precedent:1"),
    ]
    rules = [
        _actionable_basis("basis.grant", when_action="restart"),
        _advisory_basis("basis.precedent", when_action="restart"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=rules)

    assert verdict.status == "denied"
    assert verdict.failed_rules == []  # no rule failed; basis simply didn't engage


def test_actionable_basis_fires_but_require_fails_yields_denied():
    """Actionable basis fired but its require contradicted (granted_scope
    is staging, not prod).  Deny-rule failure short-circuits everything."""
    facts = [Fact(subject="actor", field="granted_scope", value="staging", source="standing:1")]
    verdict = verify(PROPOSAL, facts=facts, rules=[_actionable_basis("basis.grant")])

    assert verdict.status == "denied"
    assert len(verdict.failed_rules) == 1


def test_no_basis_rules_falls_through_to_allowed():
    """Legacy behavior preserved: payloads with no basis dimension at
    all behave exactly as before — allowed if no deny-rules fail."""
    rule = ConstraintRule(
        rule_id="constraint.r1",
        description="ordinary constraint",
        kind="constraint",
        require=[ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod")],
    )
    facts = [Fact(subject="actor", field="granted_scope", value="prod", source="test")]
    verdict = verify(PROPOSAL, facts=facts, rules=[rule])

    assert verdict.status == "allowed"


def test_advisory_basis_with_failing_deny_rule_yields_denied():
    """Even with an advisory basis firing, a failed deny-severity rule
    in another dimension forces denied.  Advisory does not soften denial."""
    advisory = _advisory_basis("basis.precedent")
    constraint = ConstraintRule(
        rule_id="constraint.r1",
        description="needs metadata current",
        kind="constraint",
        require=[ConstraintAtom(subject="target", field="metadata_current", op="eq", value="true")],
    )
    facts = [
        Fact(subject="target", field="prior_review", value="true", source="precedent:1"),
        Fact(subject="target", field="metadata_current", value="false", source="meta:1"),
    ]
    verdict = verify(PROPOSAL, facts=facts, rules=[advisory, constraint])

    assert verdict.status == "denied"


def test_advisory_basis_does_not_fire_yields_denied():
    """Only an advisory basis is submitted, but its when-clause doesn't
    match.  No basis fired → denied."""
    rules = [_advisory_basis("basis.precedent", when_action="restart")]
    facts = [Fact(subject="target", field="prior_review", value="true", source="precedent:1")]
    verdict = verify(PROPOSAL, facts=facts, rules=rules)

    assert verdict.status == "denied"


# ------------------------------------------------------------------
# Schema validation
# ------------------------------------------------------------------

class TestBasisEffectValidation:
    """basis_effect='advisory' is meaningful only on basis rules.
    Setting it on any other kind is a schema error, not a soft default."""

    def test_advisory_on_non_basis_kind_rejected(self):
        with pytest.raises(Exception, match="basis_effect"):
            ConstraintRule(
                rule_id="r.1",
                description="d",
                kind="constraint",
                basis_effect="advisory",
            )

    def test_actionable_on_non_basis_kind_accepted(self):
        """actionable is the default; explicitly setting it on a
        non-basis rule is harmless and accepted."""
        r = ConstraintRule(
            rule_id="r.1",
            description="d",
            kind="constraint",
            basis_effect="actionable",
        )
        assert r.basis_effect == "actionable"

    @pytest.mark.parametrize("effect", ["actionable", "advisory"])
    def test_either_effect_on_basis_kind_accepted(self, effect):
        r = ConstraintRule(
            rule_id="r.1",
            description="d",
            kind="basis",
            basis_effect=effect,
        )
        assert r.basis_effect == effect

    def test_basis_effect_defaults_to_actionable(self):
        r = ConstraintRule(rule_id="r.1", description="d", kind="basis")
        assert r.basis_effect == "actionable"
