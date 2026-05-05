"""Cross-surface fixture tests for runner.run_payload.

The same fixtures live in tests/fixtures/ and are reused by test_cli
and test_mcp.  Any verdict produced through one surface should match
the verdict produced through the others.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import PayloadError, run_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_allowed_fixture():
    verdict = run_payload(_load("allowed.json"))
    assert verdict.status == "allowed"
    assert verdict.failed_rules == []
    assert verdict.warnings == []


def test_denied_fixture():
    verdict = run_payload(_load("denied.json"))
    assert verdict.status == "denied"
    failed_ids = {r.rule_id for r in verdict.failed_rules}
    assert "standing.scope_match" in failed_ids


def test_invalid_fixture():
    verdict = run_payload(_load("invalid.json"))
    assert verdict.status == "invalid_input"
    assert len(verdict.contradictions) == 1
    assert verdict.contradictions[0].subject == "actor"
    assert verdict.contradictions[0].field == "granted_scope"


def test_missing_top_level_keys():
    with pytest.raises(PayloadError, match="missing required keys"):
        run_payload({"proposal": {}, "facts": []})  # missing rules


def test_non_dict_payload():
    with pytest.raises(PayloadError, match="must be a JSON object"):
        run_payload([])


def test_facts_must_be_list():
    with pytest.raises(PayloadError, match="'facts' must be a list"):
        run_payload({"proposal": {}, "facts": {}, "rules": []})


def test_rules_must_be_list():
    with pytest.raises(PayloadError, match="'rules' must be a list"):
        run_payload({"proposal": {}, "facts": [], "rules": {}})
