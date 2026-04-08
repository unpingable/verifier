"""Slice 0 tests: scope-based admissibility.

Scenario: an actor requests an action on a target under a scope.
Standing grants determine what scopes the actor has.
Continuity constraints determine what the target requires.
The verifier checks whether the proposal is admissible.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import ConstraintAtom, ConstraintRule, Fact, Proposal
from verifier import verify


# ------------------------------------------------------------------
# Rules
# ------------------------------------------------------------------

SCOPE_RULE = ConstraintRule(
    rule_id="standing.scope_match",
    description="Requested action must be within the actor's granted scope",
    when=[
        ConstraintAtom(subject="proposal", field="action", op="eq", value="deploy"),
    ],
    require=[
        ConstraintAtom(subject="actor", field="granted_scope", op="eq", value="deploy"),
    ],
    severity="deny",
)

POLICY_RULE = ConstraintRule(
    rule_id="continuity.policy_required",
    description="Target must have an active policy fact for the requested action",
    when=[
        ConstraintAtom(subject="proposal", field="action", op="eq", value="deploy"),
    ],
    require=[
        ConstraintAtom(subject="target", field="deploy_policy", op="eq", value="active"),
    ],
    severity="deny",
)

REVIEW_WARNING = ConstraintRule(
    rule_id="custody.review_fresh",
    description="Target should have a recent review (warning only)",
    when=[
        ConstraintAtom(subject="proposal", field="action", op="eq", value="deploy"),
    ],
    require=[
        ConstraintAtom(subject="target", field="review_current", op="eq", value="true"),
    ],
    severity="warn",
)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestScopeVerifier:
    """Basic scope admissibility checks."""

    def test_allowed_when_all_constraints_met(self):
        proposal = Proposal(action="deploy", actor="ci-bot", target="api-service", scope="deploy")
        facts = [
            Fact(subject="actor", field="granted_scope", value="deploy", source="standing:grant-001"),
            Fact(subject="target", field="deploy_policy", value="active", source="continuity:mem-042"),
            Fact(subject="target", field="review_current", value="true", source="custody:grant-099"),
        ]
        verdict = verify(proposal, facts, [SCOPE_RULE, POLICY_RULE, REVIEW_WARNING])

        assert verdict.status == "allowed"
        assert verdict.failed_rules == []
        assert verdict.warnings == []

    def test_denied_when_scope_missing(self):
        proposal = Proposal(action="deploy", actor="rogue-bot", target="api-service", scope="deploy")
        facts = [
            # Actor has read scope, not deploy
            Fact(subject="actor", field="granted_scope", value="read", source="standing:grant-002"),
            Fact(subject="target", field="deploy_policy", value="active", source="continuity:mem-042"),
            Fact(subject="target", field="review_current", value="true", source="custody:grant-099"),
        ]
        verdict = verify(proposal, facts, [SCOPE_RULE, POLICY_RULE, REVIEW_WARNING])

        assert verdict.status == "denied"
        assert any(r.rule_id == "standing.scope_match" for r in verdict.failed_rules)

    def test_denied_when_policy_missing(self):
        proposal = Proposal(action="deploy", actor="ci-bot", target="api-service", scope="deploy")
        facts = [
            Fact(subject="actor", field="granted_scope", value="deploy", source="standing:grant-001"),
            # Policy is inactive
            Fact(subject="target", field="deploy_policy", value="inactive", source="continuity:mem-042"),
            Fact(subject="target", field="review_current", value="true", source="custody:grant-099"),
        ]
        verdict = verify(proposal, facts, [SCOPE_RULE, POLICY_RULE, REVIEW_WARNING])

        assert verdict.status == "denied"
        assert any(r.rule_id == "continuity.policy_required" for r in verdict.failed_rules)

    def test_denied_reports_multiple_failing_rules(self):
        proposal = Proposal(action="deploy", actor="rogue-bot", target="api-service", scope="deploy")
        facts = [
            Fact(subject="actor", field="granted_scope", value="read", source="standing:grant-002"),
            Fact(subject="target", field="deploy_policy", value="inactive", source="continuity:mem-042"),
        ]
        verdict = verify(proposal, facts, [SCOPE_RULE, POLICY_RULE])

        assert verdict.status == "denied"
        failed_ids = {r.rule_id for r in verdict.failed_rules}
        assert "standing.scope_match" in failed_ids
        assert "continuity.policy_required" in failed_ids

    def test_non_matching_action_passes_unconditionally(self):
        """Rules only fire for deploy; a read action should pass."""
        proposal = Proposal(action="read", actor="anyone", target="api-service", scope="read")
        facts = [
            # No deploy-related facts needed
            Fact(subject="actor", field="granted_scope", value="read", source="standing:grant-003"),
        ]
        verdict = verify(proposal, facts, [SCOPE_RULE, POLICY_RULE, REVIEW_WARNING])

        assert verdict.status == "allowed"

    def test_unconditional_rule(self):
        """A rule with empty `when` applies to every proposal."""
        always_deny = ConstraintRule(
            rule_id="lockdown.global",
            description="System is in lockdown, no actions permitted",
            when=[],
            require=[
                ConstraintAtom(subject="system", field="lockdown", op="eq", value="false"),
            ],
            severity="deny",
        )
        proposal = Proposal(action="read", actor="anyone", target="anything", scope="read")
        facts = [
            Fact(subject="system", field="lockdown", value="true"),
        ]
        verdict = verify(proposal, facts, [always_deny])

        assert verdict.status == "denied"
        assert verdict.failed_rules[0].rule_id == "lockdown.global"

    def test_set_membership_in(self):
        """Test the 'in' operator for scope checking."""
        scope_rule = ConstraintRule(
            rule_id="standing.allowed_actions",
            description="Actor action must be in allowed set",
            when=[],
            require=[
                ConstraintAtom(
                    subject="proposal", field="action",
                    op="in", value=["read", "list", "describe"],
                ),
            ],
            severity="deny",
        )
        # Action is "deploy" which is NOT in the allowed set
        proposal = Proposal(action="deploy", actor="ci-bot", target="api-service", scope="deploy")
        facts = []
        verdict = verify(proposal, facts, [scope_rule])

        assert verdict.status == "denied"
        assert verdict.failed_rules[0].rule_id == "standing.allowed_actions"

    def test_set_membership_in_passes(self):
        scope_rule = ConstraintRule(
            rule_id="standing.allowed_actions",
            description="Actor action must be in allowed set",
            when=[],
            require=[
                ConstraintAtom(
                    subject="proposal", field="action",
                    op="in", value=["read", "list", "deploy"],
                ),
            ],
            severity="deny",
        )
        proposal = Proposal(action="deploy", actor="ci-bot", target="api-service", scope="deploy")
        facts = []
        verdict = verify(proposal, facts, [scope_rule])

        assert verdict.status == "allowed"

    def test_verdict_includes_used_facts(self):
        proposal = Proposal(action="deploy", actor="ci-bot", target="api-service", scope="deploy")
        facts = [
            Fact(subject="actor", field="granted_scope", value="deploy", source="standing:grant-001"),
            Fact(subject="target", field="deploy_policy", value="active", source="continuity:mem-042"),
        ]
        verdict = verify(proposal, facts, [SCOPE_RULE, POLICY_RULE])

        assert verdict.status == "allowed"
        assert len(verdict.used_facts) == 2
        assert all(f.source is not None for f in verdict.used_facts)
