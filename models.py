"""Typed IR for the verifier sidecar.

Domain systems (continuity, standing, custody, cadence, NQ, governor)
adapt their state into these types.  The verifier does not know their
internals -- it only sees proposals, facts, and constraint rules.

Schema version: 0.1.0
Stability: inputs (Proposal, Fact, ConstraintRule) and outputs (Verdict)
are frozen at the field level.  New fields may be added with defaults.
Existing fields will not be removed or change type without a major
version bump.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = "0.1.0"


# ------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------

class Proposal(BaseModel):
    """An action request under evaluation.

    All fields are required and non-empty.
    """
    action: str = Field(..., min_length=1)
    actor: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    scope: str = Field(..., min_length=1)


class Fact(BaseModel):
    """A typed assertion about current world state.

    Facts come from upstream systems (standing grants, continuity
    memories, cadence contracts, etc.).  The verifier treats them as
    ground truth for the purpose of constraint checking.

    Contract for adapters:
    - subject: the entity class (e.g., "actor", "target", "proposal",
      "system", "policy").  Must be non-empty.
    - field: the property name within that subject.  Must be non-empty.
    - value: the asserted value.  Booleans and ints are normalized to
      their string representation ("true"/"false", "42") inside the
      solver.  Adapters may pass native types; the compiler handles
      normalization.
    - source: provenance identifier tracing this fact back to its
      origin (e.g., "standing:grant-<uuid>", "continuity:<memory_id>").
      Required — facts without provenance are not verifiable.
    """
    subject: str = Field(..., min_length=1)
    field: str = Field(..., min_length=1)
    value: str | int | bool
    source: str = Field(..., min_length=1)


# ------------------------------------------------------------------
# Constraint IR
# ------------------------------------------------------------------

class ConstraintAtom(BaseModel):
    """Single predicate: subject.field op value."""
    subject: str = Field(..., min_length=1)
    field: str = Field(..., min_length=1)
    op: Literal["eq", "neq", "in", "not_in"]
    value: str | int | bool | list[str]

    @field_validator("value")
    @classmethod
    def validate_list_ops(cls, v, info):
        op = info.data.get("op")
        if op in ("in", "not_in") and not isinstance(v, list):
            raise ValueError(f"'{op}' operator requires list value")
        if op in ("eq", "neq") and isinstance(v, list):
            raise ValueError(f"'{op}' operator requires scalar value")
        return v


class ConstraintRule(BaseModel):
    """Named rule: when all `when` atoms match, all `require` atoms
    must also hold.  If any `require` atom fails, the rule fires.

    Empty `when` means the rule applies unconditionally.
    """
    rule_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    when: list[ConstraintAtom] = []
    require: list[ConstraintAtom] = []
    severity: Literal["deny", "warn"] = "deny"


# ------------------------------------------------------------------
# Output
# ------------------------------------------------------------------

class FailedRule(BaseModel):
    """One rule that contributed to denial or warning."""
    rule_id: str
    description: str
    severity: Literal["deny", "warn"]


class MissingFact(BaseModel):
    """A (subject, field) pair required by a rule but not grounded by any fact."""
    rule_id: str
    subject: str
    field: str


class FactContradiction(BaseModel):
    """Two or more facts that assert different values for the same (subject, field)."""
    subject: str
    field: str
    facts: list[Fact]


class Verdict(BaseModel):
    """Verifier output.  Governor or other consumers wrap this
    into their own receipts -- the verifier does not produce
    governance decisions, only solver verdicts.

    Status semantics:
    - allowed: all deny-severity rules satisfied
    - denied: one or more deny-severity rules violated
    - invalid_input: fact set is internally contradictory;
      rules were not evaluated

    Schema version is included so consumers can detect drift.
    """
    schema_version: str = SCHEMA_VERSION
    status: Literal["allowed", "denied", "invalid_input"]
    failed_rules: list[FailedRule] = []
    used_facts: list[Fact] = []
    warnings: list[FailedRule] = []
    missing_facts: list[MissingFact] = []
    contradictions: list[FactContradiction] = []
