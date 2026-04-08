"""Verifier: the stern little solver.

Takes a proposal, a set of facts, and a set of constraint rules.
Returns a Verdict saying whether the proposal is admissible and,
if not, which named rules caused denial.

Each rule is checked independently against the grounded proposal
and facts.  This gives *all* failing rules, not just a minimal
unsat core (which Z3 would minimize, potentially hiding violations
that governance needs to see).

This is a *verifier*, not a governor.  It emits verdicts;
governance decisions happen downstream.
"""

from __future__ import annotations

from z3 import BoolVal, Solver, StringVal, unsat

from compiler import _has_fact, compile_fact, compile_proposal, compile_rule_into
from models import (
    ConstraintRule,
    Fact,
    FailedRule,
    MissingFact,
    Proposal,
    Verdict,
)


def _grounded_keys(proposal: Proposal, facts: list[Fact]) -> set[tuple[str, str]]:
    """Return the set of (subject, field) pairs grounded by the proposal and facts."""
    keys = {
        ("proposal", "action"),
        ("proposal", "actor"),
        ("proposal", "target"),
        ("proposal", "scope"),
    }
    for f in facts:
        keys.add((f.subject, f.field))
    return keys


def _referenced_keys(rule: ConstraintRule) -> set[tuple[str, str]]:
    """Return all (subject, field) pairs referenced in a rule's atoms (when + require)."""
    keys: set[tuple[str, str]] = set()
    for a in rule.when:
        keys.add((a.subject, a.field))
    for a in rule.require:
        keys.add((a.subject, a.field))
    return keys


def _require_keys(rule: ConstraintRule) -> set[tuple[str, str]]:
    """Return (subject, field) pairs referenced only in require atoms."""
    return {(a.subject, a.field) for a in rule.require}


def _active_rule(rule: ConstraintRule, grounded: set[tuple[str, str]]) -> bool:
    """Check if a rule's when-clause references are all grounded."""
    for a in rule.when:
        if (a.subject, a.field) not in grounded:
            return False
    return True


def _check_rule(
    proposal: Proposal,
    facts: list[Fact],
    rule: ConstraintRule,
) -> bool:
    """Check one rule against grounded proposal + facts.

    Returns True if the rule is satisfied, False if violated.
    """
    solver = Solver()

    grounded = _grounded_keys(proposal, facts)

    for assertion in compile_proposal(proposal):
        solver.add(assertion)

    for fact in facts:
        for assertion in compile_fact(fact):
            solver.add(assertion)

    # Closed-world assumption: any (subject, field) referenced by the
    # rule but not grounded by a fact or the proposal is absent.
    for subj, fld in _referenced_keys(rule) - grounded:
        solver.add(_has_fact(StringVal(subj), StringVal(fld)) == BoolVal(False))

    compile_rule_into(solver, rule)

    return solver.check() != unsat


def verify(
    proposal: Proposal,
    facts: list[Fact],
    rules: list[ConstraintRule],
) -> Verdict:
    """Check whether `proposal` is admissible given `facts` and `rules`.

    Each rule is checked independently so that *all* violations are
    reported, not just a minimal subset.

    Returns a Verdict with:
    - status: "allowed" or "denied"
    - failed_rules: deny-severity rules that were violated
    - used_facts: the facts that were asserted
    - warnings: warn-severity rules that were violated
    """
    grounded = _grounded_keys(proposal, facts)

    failed: list[FailedRule] = []
    warnings: list[FailedRule] = []
    missing: list[MissingFact] = []

    for rule in rules:
        if _check_rule(proposal, facts, rule):
            continue

        entry = FailedRule(
            rule_id=rule.rule_id,
            description=rule.description,
            severity=rule.severity,
        )
        if rule.severity == "warn":
            warnings.append(entry)
        else:
            failed.append(entry)

        # Diagnostic: identify missing facts for failed rules
        for subj, fld in _require_keys(rule) - grounded:
            missing.append(MissingFact(rule_id=rule.rule_id, subject=subj, field=fld))

    status = "denied" if failed else "allowed"

    return Verdict(
        status=status,
        failed_rules=failed,
        used_facts=facts,
        warnings=warnings,
        missing_facts=missing,
    )
