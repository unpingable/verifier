"""Typed IR for the verifier sidecar.

Domain systems (continuity, standing, custody, cadence, NQ, governor)
adapt their state into these types.  The verifier does not know their
internals -- it only sees proposals, facts, and constraint rules.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------

class Proposal(BaseModel):
    """An action request under evaluation."""
    action: str
    actor: str
    target: str
    scope: str


class Fact(BaseModel):
    """A typed assertion about current world state.

    Facts come from upstream systems (standing grants, continuity
    memories, cadence contracts, etc.).  The verifier treats them as
    ground truth for the purpose of constraint checking.
    """
    subject: str          # proposal | actor | target | policy | ...
    field: str            # action | scope | reliance_class | ...
    value: str | int | bool
    source: str | None = None   # memory_id, grant_id, receipt_hash, ...


# ------------------------------------------------------------------
# Constraint IR
# ------------------------------------------------------------------

class ConstraintAtom(BaseModel):
    """Single predicate: subject.field op value."""
    subject: str
    field: str
    op: Literal["eq", "neq", "in", "not_in"]
    value: str | int | bool | list[str]


class ConstraintRule(BaseModel):
    """Named rule: when all `when` atoms match, all `require` atoms
    must also hold.  If any `require` atom fails, the rule fires.

    Empty `when` means the rule applies unconditionally.
    """
    rule_id: str
    description: str
    when: list[ConstraintAtom] = []
    require: list[ConstraintAtom] = []
    severity: Literal["deny", "warn"] = "deny"


# ------------------------------------------------------------------
# Output
# ------------------------------------------------------------------

class FailedRule(BaseModel):
    """One rule that contributed to denial."""
    rule_id: str
    description: str
    severity: Literal["deny", "warn"]


class MissingFact(BaseModel):
    """A (subject, field) pair required by a rule but not grounded by any fact."""
    rule_id: str
    subject: str
    field: str


class FactContradiction(BaseModel):
    """Two facts that assert different values for the same (subject, field)."""
    subject: str
    field: str
    facts: list[Fact]


class Verdict(BaseModel):
    """Verifier output.  Governor or other consumers wrap this
    into their own receipts -- the verifier does not produce
    governance decisions, only solver verdicts.
    """
    status: Literal["allowed", "denied", "invalid_input"]
    failed_rules: list[FailedRule] = []
    used_facts: list[Fact] = []
    warnings: list[FailedRule] = []
    missing_facts: list[MissingFact] = []
    contradictions: list[FactContradiction] = []
