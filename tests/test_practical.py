"""Practical verifier tests — the "does it even have hands" suite.

These are embarrassingly concrete by design.  Each test uses the
same shape: worker-a wants to deploy service/api to prod.  The
facts and rules change to exercise one specific verifier behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import ConstraintAtom, ConstraintRule, Fact, MissingFact, Proposal
from verifier import verify


# ------------------------------------------------------------------
# Shared fixtures
# ------------------------------------------------------------------

PROPOSAL = Proposal(action="deploy", actor="worker-a", target="service/api", scope="prod")

SCOPE_RULE = ConstraintRule(
    rule_id="standing.scope_match",
    description="Requested scope must match the actor's granted scope for this action/target",
    when=[
        ConstraintAtom(subject="proposal", field="action", op="eq", value="deploy"),
        ConstraintAtom(subject="proposal", field="target", op="eq", value="service/api"),
    ],
    require=[
        ConstraintAtom(subject="proposal", field="scope", op="eq", value="prod"),
        ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="prod"),
    ],
    severity="deny",
)

FREEZE_RULE = ConstraintRule(
    rule_id="continuity.freeze_override",
    description="Deploy to prod requires freeze_override=true when target is frozen",
    when=[
        ConstraintAtom(subject="proposal", field="action", op="eq", value="deploy"),
        ConstraintAtom(subject="proposal", field="scope", op="eq", value="prod"),
        ConstraintAtom(subject="target", field="frozen", op="eq", value="true"),
    ],
    require=[
        ConstraintAtom(subject="target", field="freeze_override", op="eq", value="true"),
    ],
    severity="deny",
)

STALE_ADVISORY_RULE = ConstraintRule(
    rule_id="advisory.stale_metadata",
    description="Target has stale advisory metadata",
    when=[
        ConstraintAtom(subject="proposal", field="action", op="eq", value="deploy"),
    ],
    require=[
        ConstraintAtom(subject="target", field="metadata_current", op="eq", value="true"),
    ],
    severity="warn",
)


# ------------------------------------------------------------------
# 1. Scope mismatch — denied
# ------------------------------------------------------------------

class TestScopeMismatch:
    """Worker-a has a staging grant, requests prod.  Denied."""

    def test_denied_on_wrong_scope(self):
        facts = [
            Fact(subject="actor", field="granted_scope", value="staging", source="standing:grant-100"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        assert verdict.status == "denied"
        assert len(verdict.failed_rules) == 1
        assert verdict.failed_rules[0].rule_id == "standing.scope_match"

    def test_failed_rule_description_is_specific(self):
        """The explanation should point at the scope rule, not generic solver noise."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="staging", source="standing:grant-100"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        rule = verdict.failed_rules[0]
        assert "scope" in rule.description.lower()
        assert rule.rule_id == "standing.scope_match"


# ------------------------------------------------------------------
# 2. Happy path — allowed
# ------------------------------------------------------------------

class TestHappyPath:
    """Same shape, but the fact grants prod.  Allowed."""

    def test_allowed_on_matching_scope(self):
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        assert verdict.status == "allowed"
        assert verdict.failed_rules == []
        assert verdict.warnings == []

    def test_used_facts_include_matching_grant(self):
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        assert len(verdict.used_facts) == 1
        assert verdict.used_facts[0].source == "standing:grant-101"


# ------------------------------------------------------------------
# 3. Continuity-style required fact — denied
# ------------------------------------------------------------------

class TestContinuityFact:
    """Standing grant is valid, but target is frozen and no
    freeze_override fact is present.  Denied."""

    def test_denied_missing_freeze_override(self):
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="target", field="frozen", value="true", source="continuity:freeze-001"),
            # No freeze_override fact — verifier should fail closed
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, FREEZE_RULE])

        assert verdict.status == "denied"
        failed_ids = {r.rule_id for r in verdict.failed_rules}
        assert "continuity.freeze_override" in failed_ids
        # Scope rule should still pass
        assert "standing.scope_match" not in failed_ids

    def test_allowed_with_freeze_override(self):
        """Confirm the override actually works when present."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="target", field="frozen", value="true", source="continuity:freeze-001"),
            Fact(subject="target", field="freeze_override", value="true", source="continuity:override-001"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, FREEZE_RULE])

        assert verdict.status == "allowed"


# ------------------------------------------------------------------
# 4. Conflicting facts — denied
# ------------------------------------------------------------------

class TestConflictingFacts:
    """Feed contradictory facts.  The fact-consistency phase catches
    these before the solver runs and returns invalid_input with the
    specific conflicting facts and their sources.

    This separates "your rules deny this" from "your input state is
    garbage" — an important distinction for explainability.
    """

    def test_contradictory_facts_return_invalid_input(self):
        """Contradictory frozen facts → invalid_input, not denied."""
        facts = [
            Fact(subject="target", field="frozen", value="true", source="continuity:freeze-001"),
            Fact(subject="target", field="frozen", value="false", source="continuity:freeze-002"),
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, FREEZE_RULE])

        assert verdict.status == "invalid_input"
        assert len(verdict.contradictions) == 1
        c = verdict.contradictions[0]
        assert c.subject == "target"
        assert c.field == "frozen"
        assert len(c.facts) == 2
        sources = {f.source for f in c.facts}
        assert "continuity:freeze-001" in sources
        assert "continuity:freeze-002" in sources

    def test_contradictory_grant_returns_invalid_input(self):
        """Contradictory scope facts → invalid_input with source ids."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="actor", field="granted_scope", value="staging", source="standing:grant-102"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        assert verdict.status == "invalid_input"
        assert len(verdict.contradictions) == 1
        c = verdict.contradictions[0]
        assert c.subject == "actor"
        assert c.field == "granted_scope"

    def test_no_rules_evaluated_on_invalid_input(self):
        """When input is invalid, rules are not evaluated at all."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="actor", field="granted_scope", value="staging", source="standing:grant-102"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        assert verdict.status == "invalid_input"
        assert verdict.failed_rules == []
        assert verdict.warnings == []
        assert verdict.missing_facts == []

    def test_multiple_contradictions_all_reported(self):
        """Multiple contradictory pairs → all reported."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="s:1"),
            Fact(subject="actor", field="granted_scope", value="staging", source="s:2"),
            Fact(subject="target", field="frozen", value="true", source="c:1"),
            Fact(subject="target", field="frozen", value="false", source="c:2"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, FREEZE_RULE])

        assert verdict.status == "invalid_input"
        assert len(verdict.contradictions) == 2

    def test_duplicate_same_value_is_not_contradiction(self):
        """Same (subject, field, value) from two sources is redundant, not contradictory."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-103"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE])

        # Same value from two sources — not a contradiction
        assert verdict.status != "invalid_input"


# ------------------------------------------------------------------
# 5. Missing fact vs false fact
# ------------------------------------------------------------------

class TestMissingVsFalseFact:
    """Distinguish absence of evidence from evidence of absence.

    - Missing required fact → fail closed (rule unsat because the
      solver has no grounding for the required field)
    - Explicit false fact → fail with the specific rule it violates

    Both deny, but for different reasons the verifier can surface.
    """

    def test_missing_fact_fails_closed(self):
        """No freeze_override fact at all.  Rule requires it → denied.
        Diagnostic should identify the missing (subject, field) pair."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="target", field="frozen", value="true", source="continuity:freeze-001"),
            # freeze_override simply absent
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, FREEZE_RULE])

        assert verdict.status == "denied"
        failed_ids = {r.rule_id for r in verdict.failed_rules}
        assert "continuity.freeze_override" in failed_ids

        # Diagnostic: verifier identifies the missing fact
        assert len(verdict.missing_facts) >= 1
        missing = verdict.missing_facts[0]
        assert missing.rule_id == "continuity.freeze_override"
        assert missing.subject == "target"
        assert missing.field == "freeze_override"

    def test_explicit_false_fact_fails_with_rule(self):
        """freeze_override explicitly set to false.  Still denied,
        but the fact is present in used_facts."""
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="target", field="frozen", value="true", source="continuity:freeze-001"),
            Fact(subject="target", field="freeze_override", value="false", source="continuity:override-denied"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, FREEZE_RULE])

        assert verdict.status == "denied"
        failed_ids = {r.rule_id for r in verdict.failed_rules}
        assert "continuity.freeze_override" in failed_ids
        # The false fact should be in used_facts — it's evidence, not absence
        override_facts = [f for f in verdict.used_facts if f.field == "freeze_override"]
        assert len(override_facts) == 1
        assert override_facts[0].value == "false"


# ------------------------------------------------------------------
# 6. Warn vs deny
# ------------------------------------------------------------------

class TestWarnVsDeny:
    """One rule with severity='warn'.  Deploy is allowed,
    but warnings are populated."""

    def test_allowed_with_warning(self):
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            # metadata_current is stale → triggers warn rule
            Fact(subject="target", field="metadata_current", value="false", source="advisory:meta-001"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, STALE_ADVISORY_RULE])

        assert verdict.status == "allowed"
        assert verdict.failed_rules == []
        assert len(verdict.warnings) == 1
        assert verdict.warnings[0].rule_id == "advisory.stale_metadata"
        assert verdict.warnings[0].severity == "warn"

    def test_no_warning_when_metadata_current(self):
        facts = [
            Fact(subject="actor", field="granted_scope", value="prod", source="standing:grant-101"),
            Fact(subject="target", field="metadata_current", value="true", source="advisory:meta-002"),
        ]
        verdict = verify(PROPOSAL, facts, [SCOPE_RULE, STALE_ADVISORY_RULE])

        assert verdict.status == "allowed"
        assert verdict.warnings == []
