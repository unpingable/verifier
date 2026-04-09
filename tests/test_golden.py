"""Golden fixture tests.

Hand-curated JSON fixtures that pin the verifier's wire contract.
If these break, the schema changed — that's a version bump, not a
casual fix.

These are NOT generated on each run.  They're checked-in artifacts
that catch field renames, enum spelling changes, required-field
drift, and nested payload shape changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import (
    SCHEMA_VERSION,
    Fact,
    FactContradiction,
    FailedRule,
    MissingFact,
    Proposal,
    Verdict,
)

GOLDEN = Path(__file__).parent / "golden"


def _load(name: str) -> dict:
    return json.loads((GOLDEN / name).read_text())


# ------------------------------------------------------------------
# Round-trip: fixture JSON → model → JSON == fixture
# ------------------------------------------------------------------

class TestRoundTrip:
    """Load fixture, parse into model, dump back.  Must match exactly."""

    def test_proposal(self):
        data = _load("proposal_deploy.json")
        assert Proposal.model_validate(data).model_dump(mode="json") == data

    def test_fact(self):
        data = _load("fact_standing_grant.json")
        assert Fact.model_validate(data).model_dump(mode="json") == data

    def test_verdict_allowed(self):
        data = _load("verdict_allowed.json")
        assert Verdict.model_validate(data).model_dump(mode="json") == data

    def test_verdict_denied_missing_fact(self):
        data = _load("verdict_denied_missing_fact.json")
        assert Verdict.model_validate(data).model_dump(mode="json") == data

    def test_verdict_invalid_input(self):
        data = _load("verdict_invalid_input.json")
        assert Verdict.model_validate(data).model_dump(mode="json") == data


# ------------------------------------------------------------------
# Schema version tripwire
# ------------------------------------------------------------------

class TestSchemaVersionInFixtures:
    """Every verdict fixture must match the current SCHEMA_VERSION."""

    def test_verdict_allowed_version(self):
        assert _load("verdict_allowed.json")["schema_version"] == SCHEMA_VERSION

    def test_verdict_denied_version(self):
        assert _load("verdict_denied_missing_fact.json")["schema_version"] == SCHEMA_VERSION

    def test_verdict_invalid_input_version(self):
        assert _load("verdict_invalid_input.json")["schema_version"] == SCHEMA_VERSION


# ------------------------------------------------------------------
# Construction: build model from code, compare to fixture
# ------------------------------------------------------------------

class TestConstruction:
    """Build verdicts from code the way the verifier does, compare to fixture."""

    def test_allowed_verdict_matches_fixture(self):
        verdict = Verdict(
            status="allowed",
            used_facts=[
                Fact(subject="actor", field="granted_scope", value="prod",
                     source="standing:grant-a1b2c3d4"),
            ],
        )
        assert verdict.model_dump(mode="json") == _load("verdict_allowed.json")

    def test_denied_verdict_matches_fixture(self):
        verdict = Verdict(
            status="denied",
            failed_rules=[
                FailedRule(
                    rule_id="continuity.freeze_override",
                    description="Deploy to prod requires freeze_override when target is frozen",
                    severity="deny",
                ),
            ],
            used_facts=[
                Fact(subject="actor", field="granted_scope", value="prod",
                     source="standing:grant-a1b2c3d4"),
                Fact(subject="target", field="frozen", value="true",
                     source="continuity:freeze-001"),
            ],
            missing_facts=[
                MissingFact(
                    rule_id="continuity.freeze_override",
                    subject="target",
                    field="freeze_override",
                ),
            ],
        )
        assert verdict.model_dump(mode="json") == _load("verdict_denied_missing_fact.json")

    def test_invalid_input_verdict_matches_fixture(self):
        conflicting_facts = [
            Fact(subject="target", field="frozen", value="true",
                 source="continuity:freeze-001"),
            Fact(subject="target", field="frozen", value="false",
                 source="continuity:freeze-002"),
        ]
        verdict = Verdict(
            status="invalid_input",
            used_facts=conflicting_facts,
            contradictions=[
                FactContradiction(
                    subject="target",
                    field="frozen",
                    facts=conflicting_facts,
                ),
            ],
        )
        assert verdict.model_dump(mode="json") == _load("verdict_invalid_input.json")
