"""Schema contract tests.

These verify that the verifier's IR types enforce their contracts:
required fields, non-empty constraints, operator/value alignment,
and version tracking.

If a test here breaks, the schema contract changed — that's a
major version event, not a casual fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import (
    SCHEMA_VERSION,
    ConstraintAtom,
    ConstraintRule,
    Fact,
    Proposal,
    Verdict,
)


class TestSchemaVersion:
    def test_version_is_semver(self):
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_verdict_includes_version(self):
        v = Verdict(status="allowed")
        assert v.schema_version == SCHEMA_VERSION


class TestProposalContract:
    def test_requires_all_fields(self):
        with pytest.raises(Exception):
            Proposal()

    def test_rejects_empty_action(self):
        with pytest.raises(Exception):
            Proposal(action="", actor="a", target="t", scope="s")

    def test_rejects_empty_actor(self):
        with pytest.raises(Exception):
            Proposal(action="a", actor="", target="t", scope="s")

    def test_rejects_empty_target(self):
        with pytest.raises(Exception):
            Proposal(action="a", actor="a", target="", scope="s")

    def test_rejects_empty_scope(self):
        with pytest.raises(Exception):
            Proposal(action="a", actor="a", target="t", scope="")

    def test_accepts_valid(self):
        p = Proposal(action="deploy", actor="bot", target="api", scope="prod")
        assert p.action == "deploy"


class TestFactContract:
    def test_requires_source(self):
        with pytest.raises(Exception):
            Fact(subject="actor", field="scope", value="prod")

    def test_rejects_empty_source(self):
        with pytest.raises(Exception):
            Fact(subject="actor", field="scope", value="prod", source="")

    def test_rejects_empty_subject(self):
        with pytest.raises(Exception):
            Fact(subject="", field="scope", value="prod", source="s:1")

    def test_rejects_empty_field(self):
        with pytest.raises(Exception):
            Fact(subject="actor", field="", value="prod", source="s:1")

    def test_accepts_string_value(self):
        f = Fact(subject="actor", field="scope", value="prod", source="s:1")
        assert f.value == "prod"

    def test_accepts_bool_value(self):
        f = Fact(subject="target", field="frozen", value=True, source="c:1")
        assert f.value is True

    def test_accepts_int_value(self):
        f = Fact(subject="target", field="priority", value=42, source="c:1")
        assert f.value == 42


class TestConstraintAtomContract:
    def test_eq_rejects_list_value(self):
        with pytest.raises(Exception):
            ConstraintAtom(subject="s", field="f", op="eq", value=["a", "b"])

    def test_neq_rejects_list_value(self):
        with pytest.raises(Exception):
            ConstraintAtom(subject="s", field="f", op="neq", value=["a", "b"])

    def test_in_rejects_scalar_value(self):
        with pytest.raises(Exception):
            ConstraintAtom(subject="s", field="f", op="in", value="scalar")

    def test_not_in_rejects_scalar_value(self):
        with pytest.raises(Exception):
            ConstraintAtom(subject="s", field="f", op="not_in", value="scalar")

    def test_in_accepts_list(self):
        a = ConstraintAtom(subject="s", field="f", op="in", value=["a", "b"])
        assert a.value == ["a", "b"]

    def test_eq_accepts_scalar(self):
        a = ConstraintAtom(subject="s", field="f", op="eq", value="x")
        assert a.value == "x"

    def test_rejects_empty_subject(self):
        with pytest.raises(Exception):
            ConstraintAtom(subject="", field="f", op="eq", value="x")

    def test_rejects_empty_field(self):
        with pytest.raises(Exception):
            ConstraintAtom(subject="s", field="", op="eq", value="x")


class TestConstraintRuleContract:
    def test_rejects_empty_rule_id(self):
        with pytest.raises(Exception):
            ConstraintRule(rule_id="", description="d")

    def test_rejects_empty_description(self):
        with pytest.raises(Exception):
            ConstraintRule(rule_id="r", description="")

    def test_accepts_valid(self):
        r = ConstraintRule(rule_id="r.1", description="a rule")
        assert r.severity == "deny"
        assert r.when == []
        assert r.require == []


class TestVerdictContract:
    def test_allowed_verdict_shape(self):
        v = Verdict(status="allowed")
        assert v.schema_version == SCHEMA_VERSION
        assert v.failed_rules == []
        assert v.warnings == []
        assert v.missing_facts == []
        assert v.contradictions == []

    def test_denied_verdict_shape(self):
        v = Verdict(status="denied")
        assert v.schema_version == SCHEMA_VERSION

    def test_invalid_input_verdict_shape(self):
        v = Verdict(status="invalid_input")
        assert v.schema_version == SCHEMA_VERSION

    def test_rejects_unknown_status(self):
        with pytest.raises(Exception):
            Verdict(status="maybe")
