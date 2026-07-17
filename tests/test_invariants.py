"""Soul-of-the-thing invariants.

Verifier is not the judge.  It is the refusal of imaginary evidence.

If a rule requires a fact and the fact is not present, the verifier
must deny — not satisfy the rule by inventing a value.  This is the
closed-world assumption, and it is the difference between this verifier
and a SAT solver pointed at hopeful inputs.

Anything that breaks this is not a bug.  It is the verifier ceasing
to mean what it says it means.
"""

from __future__ import annotations

from models import ConstraintAtom, ConstraintRule, Fact, Proposal
from verifier import verify


PROPOSAL = Proposal(action="deploy", actor="worker-a", target="service/api", scope="prod")

UNCONDITIONAL_REQUIRES_X = ConstraintRule(
    rule_id="invariant.requires_x",
    description="Unconditional rule that requires target.x == 'y'",
    when=[],  # always active
    require=[ConstraintAtom(subject="target", field="x", op="eq", value="y")],
    severity="deny",
)


def test_absence_denies_not_imagines():
    """No fact for target.x.  The solver must NOT invent x='y' to satisfy
    the rule.  Denial is the only correct outcome, and the missing fact
    must surface in the diagnostic."""
    verdict = verify(PROPOSAL, facts=[], rules=[UNCONDITIONAL_REQUIRES_X])

    assert verdict.status == "denied"
    assert len(verdict.failed_rules) == 1
    assert verdict.failed_rules[0].rule_id == "invariant.requires_x"

    missing = [m for m in verdict.missing_facts if m.rule_id == "invariant.requires_x"]
    assert len(missing) == 1
    assert missing[0].subject == "target"
    assert missing[0].field == "x"


def test_presence_allows():
    """Sanity counterweight: with the fact present, the same rule passes.
    Confirms the deny above is closed-world, not a stuck rule."""
    facts = [Fact(subject="target", field="x", value="y", source="test:fixture")]
    verdict = verify(PROPOSAL, facts=facts, rules=[UNCONDITIONAL_REQUIRES_X])

    assert verdict.status == "allowed"
    assert verdict.failed_rules == []
    assert verdict.missing_facts == []


def test_solver_unknown_cannot_produce_allowed(monkeypatch):
    """A solver `unknown` result must fail closed.

    Z3's check() returns sat / unsat / unknown.  With the current finite
    string theory `unknown` is unreachable, but the guarantee has to hold
    in code, not by accident of the theory: an undecided rule is not a
    satisfied rule.  This pins the seam that `check() != unsat` would
    reopen (unknown counted as pass).  See VERIFIER_FAIL_LOGICAL_GAP.md
    ("UNKNOWN is refusal")."""
    import z3

    monkeypatch.setattr(z3.Solver, "check", lambda self, *a, **k: z3.unknown)

    # Same inputs as test_presence_allows — would be `allowed` if the
    # solver could decide.  With the solver undecided, it must not be.
    facts = [Fact(subject="target", field="x", value="y", source="test:fixture")]
    verdict = verify(PROPOSAL, facts=facts, rules=[UNCONDITIONAL_REQUIRES_X])

    assert verdict.status != "allowed"
    assert verdict.status == "denied"
    assert [f.rule_id for f in verdict.failed_rules] == ["invariant.requires_x"]
