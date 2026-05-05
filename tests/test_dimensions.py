"""Per-dimension verdict projection.

Verifier groups rules by `kind` and emits a DimensionVerdict for each
kind that has at least one rule in the input.  This lets consumers
diagnose which admissibility dimension failed without re-correlating
rule_ids back to kinds themselves.

Status semantics under test:
- passed:  no deny-severity rule of this kind failed
- missing: every failed rule of this kind has all-ungrounded require atoms
           (closed-world denial; "give me the fact and it may pass")
- failed:  at least one failed rule of this kind had a require-atom whose
           (subject, field) was grounded but contradicted (evidence against)

The point of distinguishing missing from failed is operational: a missing
verdict tells the consumer "you have a gap in evidence," while failed
tells them "the evidence you have refutes this rule."
"""

from __future__ import annotations

from models import ConstraintAtom, ConstraintRule, Fact, Proposal
from verifier import verify


PROPOSAL = Proposal(action="deploy", actor="worker-a", target="service/api", scope="prod")


def _basis_rule(rule_id: str = "basis.r1") -> ConstraintRule:
    return ConstraintRule(
        rule_id=rule_id,
        description="basis dimension rule",
        kind="basis",
        require=[ConstraintAtom(subject="target", field="basis_ok", op="eq", value="true")],
    )


def _standing_rule(rule_id: str = "standing.r1") -> ConstraintRule:
    return ConstraintRule(
        rule_id=rule_id,
        description="standing dimension rule",
        kind="standing",
        require=[ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod")],
    )


def _precedence_rule(rule_id: str = "precedence.r1") -> ConstraintRule:
    return ConstraintRule(
        rule_id=rule_id,
        description="precedence dimension rule",
        kind="precedence",
        require=[ConstraintAtom(subject="proposal", field="scope", op="eq", value="prod")],
    )


def test_no_rules_yields_empty_dimension_verdicts():
    verdict = verify(PROPOSAL, facts=[], rules=[])
    assert verdict.dimension_verdicts == {}


def test_only_kinds_in_input_appear_in_output():
    """Absence of a key means 'no rules of this kind submitted', NOT
    'passed by default'.  This invariant matters because consumers should
    not infer a clean bill of health from silence."""
    facts = [Fact(subject="actor", field="granted_scope", value="prod", source="test")]
    verdict = verify(PROPOSAL, facts=facts, rules=[_standing_rule()])

    assert set(verdict.dimension_verdicts.keys()) == {"standing"}
    assert "basis" not in verdict.dimension_verdicts
    assert "precedence" not in verdict.dimension_verdicts
    assert "constraint" not in verdict.dimension_verdicts


def test_single_passing_rule_yields_passed():
    facts = [Fact(subject="target", field="basis_ok", value="true", source="test")]
    verdict = verify(PROPOSAL, facts=facts, rules=[_basis_rule()])

    assert verdict.status == "allowed"
    dv = verdict.dimension_verdicts["basis"]
    assert dv.status == "passed"
    assert dv.failed_rules == []
    assert dv.missing_facts == []


def test_failure_with_missing_fact_yields_missing():
    """basis_ok is unground; closed-world denies.  Dimension says 'missing'
    so the consumer knows they only need to supply the fact."""
    verdict = verify(PROPOSAL, facts=[], rules=[_basis_rule()])

    assert verdict.status == "denied"
    dv = verdict.dimension_verdicts["basis"]
    assert dv.status == "missing"
    assert len(dv.failed_rules) == 1
    assert dv.failed_rules[0].rule_id == "basis.r1"
    assert len(dv.missing_facts) == 1
    assert dv.missing_facts[0].subject == "target"
    assert dv.missing_facts[0].field == "basis_ok"


def test_failure_with_evidence_against_yields_failed():
    """basis_ok grounded but value contradicts.  Dimension says 'failed'
    so the consumer knows the evidence on hand refutes the rule."""
    facts = [Fact(subject="target", field="basis_ok", value="false", source="test")]
    verdict = verify(PROPOSAL, facts=facts, rules=[_basis_rule()])

    assert verdict.status == "denied"
    dv = verdict.dimension_verdicts["basis"]
    assert dv.status == "failed"
    assert len(dv.failed_rules) == 1
    assert dv.missing_facts == []  # no missing facts; we had evidence-against


def test_multiple_kinds_independently_classified():
    """Three kinds, three different statuses.  Each dimension is
    classified independently of the others."""
    facts = [
        # basis: pass (basis_ok grounded and matches)
        Fact(subject="target", field="basis_ok", value="true", source="test"),
        # standing: fail with evidence-against (granted_scope grounded but wrong)
        Fact(subject="actor", field="granted_scope", value="staging", source="test"),
        # precedence: missing (proposal.scope is grounded by Proposal as "prod" — wait, that means it's grounded)
    ]
    rules = [_basis_rule(), _standing_rule(), _precedence_rule()]
    verdict = verify(PROPOSAL, facts=facts, rules=rules)

    assert verdict.dimension_verdicts["basis"].status == "passed"
    assert verdict.dimension_verdicts["standing"].status == "failed"
    # proposal.scope IS grounded (by the Proposal itself) and matches "prod"
    assert verdict.dimension_verdicts["precedence"].status == "passed"


def test_missing_when_no_evidence_at_all():
    """No facts touching the require keys at all → missing."""
    rule = ConstraintRule(
        rule_id="standing.absent",
        description="needs a fact that isn't there",
        kind="standing",
        require=[ConstraintAtom(subject="actor", field="totally_absent", op="eq", value="x")],
    )
    verdict = verify(PROPOSAL, facts=[], rules=[rule])
    dv = verdict.dimension_verdicts["standing"]
    assert dv.status == "missing"


def test_warn_severity_does_not_fail_dimension():
    """Warnings populate the dimension's `warnings` list but the status
    stays `passed`.  Warnings do not deny — that's the rule-level
    invariant, and it must hold at the dimension level too."""
    rule = ConstraintRule(
        rule_id="constraint.advisory",
        description="warn-only",
        kind="constraint",
        require=[ConstraintAtom(subject="target", field="metadata_current", op="eq", value="true")],
        severity="warn",
    )
    facts = [Fact(subject="target", field="metadata_current", value="false", source="test")]
    verdict = verify(PROPOSAL, facts=facts, rules=[rule])

    assert verdict.status == "allowed"
    dv = verdict.dimension_verdicts["constraint"]
    assert dv.status == "passed"
    assert dv.failed_rules == []
    assert len(dv.warnings) == 1


def test_failed_rules_within_dimension_carry_correct_kind():
    """The FailedRule entries inside a DimensionVerdict must carry the
    matching kind.  This guards against accidental cross-kind leakage
    if grouping logic ever drifts."""
    facts = [Fact(subject="actor", field="granted_scope", value="staging", source="test")]
    rules = [_basis_rule(), _standing_rule()]
    verdict = verify(PROPOSAL, facts=facts, rules=rules)

    standing_dv = verdict.dimension_verdicts["standing"]
    for fr in standing_dv.failed_rules:
        assert fr.kind == "standing"
