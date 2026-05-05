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

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "0.2.0"

RuleKind = Literal["basis", "precedence", "standing", "constraint"]

BasisEffect = Literal["actionable", "advisory"]

ClaimState = Literal["current", "stale", "revoked", "expired"]


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
    - claim_state: lifecycle status of this evidence.  "current" facts
      are used for evaluation.  "stale", "revoked", and "expired" facts
      are filtered out of the solver pass — they do not deny by their
      mere presence (no global stale-scanning), but rules that reference
      a non-current fact's (subject, field) get a StaleFact diagnostic
      so the consumer knows their input had aged-out evidence in scope.
    """
    subject: str = Field(..., min_length=1)
    field: str = Field(..., min_length=1)
    value: str | int | bool
    source: str = Field(..., min_length=1)
    claim_state: ClaimState = "current"


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

    `kind` classifies the rule along the admissibility dimension it
    enforces.  The verifier groups rules by kind to produce
    dimension-level diagnostics (see Verdict.dimension_verdicts).
    Default is "constraint" — ordinary domain rules that don't fit one
    of the named dimensions.  This is metadata only at this layer; it
    does not change per-rule satisfaction semantics.

    `basis_effect` distinguishes actionable bases (which can support an
    `allowed` verdict) from advisory bases (which can be heard but
    cannot support action — they push the verdict to `advisory`).  Only
    valid for kind="basis"; advisory effect on any other kind is a
    schema error, not a soft default.
    """
    rule_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    kind: RuleKind = "constraint"
    basis_effect: BasisEffect = "actionable"
    when: list[ConstraintAtom] = []
    require: list[ConstraintAtom] = []
    severity: Literal["deny", "warn"] = "deny"

    @model_validator(mode="after")
    def _basis_effect_only_on_basis(self) -> ConstraintRule:
        if self.basis_effect == "advisory" and self.kind != "basis":
            raise ValueError(
                "basis_effect='advisory' is only valid for kind='basis'"
            )
        return self


# ------------------------------------------------------------------
# Output
# ------------------------------------------------------------------

class FailedRule(BaseModel):
    """One rule that contributed to denial or warning."""
    rule_id: str
    description: str
    severity: Literal["deny", "warn"]
    kind: RuleKind = "constraint"


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


class StaleFact(BaseModel):
    """A non-current fact that was excluded from evaluation but
    referenced by a rule.

    The verifier never includes stale facts in the solver pass.  But if
    a rule's atoms reference a (subject, field) for which a stale fact
    was submitted, the consumer needs to know — that's evidence they
    might have intended to count, and the closed-world denial that
    likely results would be opaque without this surfacing.

    Note: a stale fact whose (subject, field) is not referenced by any
    rule produces no StaleFact entry.  No global stale-scanning.
    """
    rule_id: str
    subject: str
    field: str
    source: str
    claim_state: ClaimState


DimensionStatus = Literal["passed", "failed", "missing"]


class DimensionVerdict(BaseModel):
    """Per-kind summary of admissibility along one dimension.

    Status semantics:
    - passed:  no deny-severity rule of this kind failed
    - missing: rules of this kind failed only because required facts
               were not grounded (closed-world denial; produce the facts
               and the rule may pass)
    - failed:  at least one rule of this kind failed with evidence
               against it (a referenced (subject, field) was grounded
               but the value contradicted the rule's require)

    Warn-severity rule violations populate `warnings` but never push the
    dimension status off `passed` — warnings do not deny.

    Only kinds that have at least one rule in the input appear in
    Verdict.dimension_verdicts.  Absence of a key means "no rules of
    this kind were submitted," not "passed by default."
    """
    status: DimensionStatus
    failed_rules: list[FailedRule] = []
    missing_facts: list[MissingFact] = []
    warnings: list[FailedRule] = []


class Verdict(BaseModel):
    """Verifier output.  Governor or other consumers wrap this
    into their own receipts -- the verifier does not produce
    governance decisions, only solver verdicts.

    Admissibility status (the trichotomy):
    - allowed:  all deny-severity rules satisfied AND, if basis rules
                are present, at least one actionable basis fired and
                held
    - advisory: all deny-severity rules satisfied AND only advisory
                bases fired (you can hear it, you cannot act on it)
    - denied:   a deny-severity rule violated, OR basis rules were
                submitted but none fired/held

    Transport / schema status (NOT part of the admissibility triad):
    - invalid_input: fact set is internally contradictory; rules were
                     not evaluated.  This is a structural failure of
                     the input, not a verdict on the proposal.

    Schema version is included so consumers can detect drift.
    """
    schema_version: str = SCHEMA_VERSION
    status: Literal["allowed", "advisory", "denied", "invalid_input"]
    failed_rules: list[FailedRule] = []
    used_facts: list[Fact] = []
    warnings: list[FailedRule] = []
    missing_facts: list[MissingFact] = []
    contradictions: list[FactContradiction] = []
    stale_facts: list[StaleFact] = []
    dimension_verdicts: dict[str, DimensionVerdict] = {}
