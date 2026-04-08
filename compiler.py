"""Compile typed IR (models.py) into Z3 constraints.

Key design rule: this module compiles *typed domain objects* to Z3,
not memory objects or raw SMT strings.  Upstream systems adapt their
state into Fact / ConstraintRule; the compiler doesn't know about
continuity internals, standing grants, etc.

Uses tracked assertions so that unsat core returns rule_ids,
not solver soup.
"""

from __future__ import annotations

from z3 import (
    BoolSort,
    Const,
    DatatypeSort,
    Function,
    IntSort,
    Or,
    Not,
    Solver,
    StringSort,
    StringVal,
    IntVal,
    BoolVal,
    sat,
    unsat,
)

from models import ConstraintAtom, ConstraintRule, Fact, Proposal


# ------------------------------------------------------------------
# Field accessor: we model the world as a function
#   field_val : (subject: String, field: String) -> String
#
# Booleans and ints are projected to their string representation
# for uniformity in slice 0.  This keeps the solver simple --
# no polymorphic sorts, no datatypes.
# ------------------------------------------------------------------

_field_val = Function("field_val", StringSort(), StringSort(), StringSort())
_has_fact = Function("has_fact", StringSort(), StringSort(), BoolSort())


def _normalize(v: str | int | bool) -> str:
    """Canonical string representation for a value."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


# ------------------------------------------------------------------
# Compile atoms
# ------------------------------------------------------------------

def compile_atom(atom: ConstraintAtom):
    """Return a Z3 boolean expression for one ConstraintAtom.

    Every atom includes a has_fact(subject, field) presence check
    so that missing facts fail closed — the solver cannot invent
    values for ungrounded fields.
    """
    from z3 import And

    subj = StringVal(atom.subject)
    fld = StringVal(atom.field)
    accessor = _field_val(subj, fld)
    present = _has_fact(subj, fld)

    if atom.op == "eq":
        return And(present, accessor == StringVal(_normalize(atom.value)))

    if atom.op == "neq":
        return And(present, accessor != StringVal(_normalize(atom.value)))

    if atom.op == "in":
        if not isinstance(atom.value, list):
            raise ValueError(f"'in' operator requires list value, got {type(atom.value)}")
        return And(present, Or([accessor == StringVal(_normalize(v)) for v in atom.value]))

    if atom.op == "not_in":
        if not isinstance(atom.value, list):
            raise ValueError(f"'not_in' operator requires list value, got {type(atom.value)}")
        return And(present, Not(Or([accessor == StringVal(_normalize(v)) for v in atom.value])))

    raise ValueError(f"Unknown operator: {atom.op}")


# ------------------------------------------------------------------
# Compile facts
# ------------------------------------------------------------------

def compile_fact(fact: Fact) -> list:
    """Return Z3 assertions for this fact: value + presence."""
    subj = StringVal(fact.subject)
    fld = StringVal(fact.field)
    return [
        _has_fact(subj, fld) == BoolVal(True),
        _field_val(subj, fld) == StringVal(_normalize(fact.value)),
    ]


# ------------------------------------------------------------------
# Compile rules (tracked)
# ------------------------------------------------------------------

def compile_rule_into(solver: Solver, rule: ConstraintRule) -> None:
    """Add a rule as a tracked assertion.

    Rule semantics: if all `when` atoms hold, then all `require`
    atoms must also hold.

    Uses solver.assert_and_track so that unsat core reports which
    rule_ids caused failure.
    """
    from z3 import And, Implies, Bool

    tracker = Bool(rule.rule_id)

    if rule.when:
        antecedent = And([compile_atom(a) for a in rule.when])
    else:
        antecedent = BoolVal(True)

    if not rule.require:
        return  # vacuous rule, nothing to enforce

    consequent = And([compile_atom(a) for a in rule.require])

    solver.assert_and_track(
        Implies(antecedent, consequent),
        tracker,
    )


# ------------------------------------------------------------------
# Compile proposal
# ------------------------------------------------------------------

def compile_proposal(proposal: Proposal) -> list:
    """Return Z3 assertions that ground the proposal fields (value + presence)."""
    assertions = []
    for field, value in [
        ("action", proposal.action),
        ("actor", proposal.actor),
        ("target", proposal.target),
        ("scope", proposal.scope),
    ]:
        subj = StringVal("proposal")
        fld = StringVal(field)
        assertions.append(_has_fact(subj, fld) == BoolVal(True))
        assertions.append(_field_val(subj, fld) == StringVal(value))
    return assertions
