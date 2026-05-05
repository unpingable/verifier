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
    DimensionVerdict,
    Fact,
    FactContradiction,
    FailedRule,
    MissingFact,
    Proposal,
    StaleFact,
    Verdict,
)


def _check_fact_consistency(facts: list[Fact]) -> list[FactContradiction]:
    """Detect contradictory facts: same (subject, field), different values.

    This is a pre-solver phase — pure Python, no Z3.  If contradictions
    exist, the verifier should return invalid_input instead of feeding
    garbage into the solver and getting incidental unsat.
    """
    from collections import defaultdict

    groups: dict[tuple[str, str], list[Fact]] = defaultdict(list)
    for f in facts:
        groups[(f.subject, f.field)].append(f)

    contradictions: list[FactContradiction] = []
    for (subj, fld), group in groups.items():
        values = {str(f.value) for f in group}
        if len(values) > 1:
            contradictions.append(FactContradiction(
                subject=subj,
                field=fld,
                facts=group,
            ))

    return contradictions


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


def _rule_fires(
    rule: ConstraintRule,
    proposal: Proposal,
    facts: list[Fact],
) -> bool:
    """Did the rule's when-clause match the current proposal + facts?

    Pure Python — no Z3 involved.  A rule that doesn't fire is not
    "satisfied" in the constructive sense; it simply isn't engaged
    by this proposal.  The distinction matters for advisory basis
    semantics, where we need to know whether a basis rule actually
    activated, not just whether it failed to deny.

    Empty when-clause → always fires (unconditional rule).
    Closed-world: any when-atom referencing an ungrounded
    (subject, field) returns False.
    """
    fact_map: dict[tuple[str, str], object] = {
        ("proposal", "action"): proposal.action,
        ("proposal", "actor"): proposal.actor,
        ("proposal", "target"): proposal.target,
        ("proposal", "scope"): proposal.scope,
    }
    for f in facts:
        fact_map[(f.subject, f.field)] = f.value

    for atom in rule.when:
        key = (atom.subject, atom.field)
        if key not in fact_map:
            return False
        actual = str(fact_map[key])
        target = atom.value
        if atom.op == "eq" and actual != str(target):
            return False
        if atom.op == "neq" and actual == str(target):
            return False
        if atom.op == "in" and actual not in [str(x) for x in target]:  # type: ignore[union-attr]
            return False
        if atom.op == "not_in" and actual in [str(x) for x in target]:  # type: ignore[union-attr]
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

    Phase 0: check fact consistency.  If contradictory facts exist,
    return invalid_input immediately — don't feed garbage into the solver.

    Phase 1: check each rule independently so that *all* violations are
    reported, not just a minimal subset.

    Returns a Verdict with:
    - status: "allowed", "advisory", "denied", or "invalid_input"
    - failed_rules: deny-severity rules that were violated
    - used_facts: the facts that were asserted (excludes non-current facts)
    - warnings: warn-severity rules that were violated
    - contradictions: conflicting facts for the same (subject, field)
    - stale_facts: non-current facts that were referenced by a rule
    - dimension_verdicts: per-kind admissibility projection
    """
    # Phase 0: fact consistency (uses current facts only — stale facts are
    # filtered before the contradiction check so an aged-out fact disagreeing
    # with a current one isn't escalated to invalid_input).
    current_facts = [f for f in facts if f.claim_state == "current"]
    non_current_facts = [f for f in facts if f.claim_state != "current"]

    contradictions = _check_fact_consistency(current_facts)
    if contradictions:
        return Verdict(
            status="invalid_input",
            used_facts=current_facts,
            contradictions=contradictions,
        )

    grounded = _grounded_keys(proposal, current_facts)

    failed: list[FailedRule] = []
    warnings: list[FailedRule] = []
    missing: list[MissingFact] = []

    for rule in rules:
        if _check_rule(proposal, current_facts, rule):
            continue

        entry = FailedRule(
            rule_id=rule.rule_id,
            description=rule.description,
            severity=rule.severity,
            kind=rule.kind,
        )
        if rule.severity == "warn":
            warnings.append(entry)
        else:
            failed.append(entry)

        # Diagnostic: identify missing facts for failed rules
        for subj, fld in _require_keys(rule) - grounded:
            missing.append(MissingFact(rule_id=rule.rule_id, subject=subj, field=fld))

    status = _aggregate_status(proposal, current_facts, rules, failed)

    dimension_verdicts = _compute_dimension_verdicts(
        rules, grounded, failed, warnings, missing,
    )

    stale_facts = _scoped_stale_facts(rules, non_current_facts)

    return Verdict(
        status=status,
        failed_rules=failed,
        used_facts=current_facts,
        warnings=warnings,
        missing_facts=missing,
        dimension_verdicts=dimension_verdicts,
        stale_facts=stale_facts,
    )


def _scoped_stale_facts(
    rules: list[ConstraintRule],
    non_current_facts: list[Fact],
) -> list[StaleFact]:
    """For each non-current fact, surface a diagnostic only if at least
    one rule actually references its (subject, field).  No global
    stale-scanning — a stale fact unrelated to any rule is irrelevant
    noise, not a denial.

    A single fact may surface multiple diagnostics, one per affected
    rule, so the consumer can correlate without re-walking the rule set.
    """
    out: list[StaleFact] = []
    for rule in rules:
        referenced = _referenced_keys(rule)
        for f in non_current_facts:
            if (f.subject, f.field) in referenced:
                out.append(StaleFact(
                    rule_id=rule.rule_id,
                    subject=f.subject,
                    field=f.field,
                    source=f.source,
                    claim_state=f.claim_state,
                ))
    return out


def _aggregate_status(
    proposal: Proposal,
    facts: list[Fact],
    rules: list[ConstraintRule],
    failed: list[FailedRule],
) -> str:
    """Roll up rule outcomes into the admissibility triad.

    Aggregation:
    1. Any deny-severity rule failed → "denied".
    2. No basis rules submitted → "allowed" (legacy behavior; the
       basis/advisory machinery only engages when basis rules are in
       play).
    3. At this point all rules — including basis rules — have passed.
       A basis rule "supports" a verdict only if it actually fired
       (its when-clause matched).  Vacuous passes (when didn't match)
       do not grant authority on this proposal.
    4. Some actionable basis fired → "allowed".
    5. Else some advisory basis fired → "advisory" (you can hear it,
       you cannot act on it).
    6. Else basis rules existed but none fired → "denied" (no basis
       to support action).
    """
    if failed:
        return "denied"

    basis_rules = [r for r in rules if r.kind == "basis"]
    if not basis_rules:
        return "allowed"

    actionable_supports = any(
        r for r in basis_rules
        if r.basis_effect == "actionable" and _rule_fires(r, proposal, facts)
    )
    if actionable_supports:
        return "allowed"

    advisory_supports = any(
        r for r in basis_rules
        if r.basis_effect == "advisory" and _rule_fires(r, proposal, facts)
    )
    if advisory_supports:
        return "advisory"

    return "denied"


def _compute_dimension_verdicts(
    rules: list[ConstraintRule],
    grounded: set[tuple[str, str]],
    failed: list[FailedRule],
    warnings: list[FailedRule],
    missing: list[MissingFact],
) -> dict[str, DimensionVerdict]:
    """Project the verdict onto the kind dimension.

    A kind only appears in the result if at least one rule of that
    kind was submitted.  Absence is "no rules of this kind," not
    "passed by default."

    Distinguishing missing from failed:
    - "missing"  — every failed rule of this kind has all its
                   require-atoms ungrounded (closed-world denial).
    - "failed"   — at least one failed rule has a require-atom whose
                   (subject, field) IS grounded; the value contradicted
                   the rule.  This is evidence-against, not absence.
    """
    rules_by_kind: dict[str, list[ConstraintRule]] = {}
    for r in rules:
        rules_by_kind.setdefault(r.kind, []).append(r)

    rule_kind_by_id = {r.rule_id: r.kind for r in rules}
    rule_by_id = {r.rule_id: r for r in rules}

    out: dict[str, DimensionVerdict] = {}
    for kind, kind_rules in rules_by_kind.items():
        kind_failed = [f for f in failed if f.kind == kind]
        kind_warnings = [w for w in warnings if w.kind == kind]
        kind_missing = [m for m in missing if rule_kind_by_id.get(m.rule_id) == kind]

        if not kind_failed:
            status = "passed"
        else:
            evidence_against = False
            for fr in kind_failed:
                rule = rule_by_id[fr.rule_id]
                if _require_keys(rule) & grounded:
                    evidence_against = True
                    break
            status = "failed" if evidence_against else "missing"

        out[kind] = DimensionVerdict(
            status=status,
            failed_rules=kind_failed,
            missing_facts=kind_missing,
            warnings=kind_warnings,
        )

    return out
