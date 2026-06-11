"""Pin the user-facing examples/ specimens against the live verifier.

The README's "30-second specimen" shows an input and the verdict it produces.
If the README claims a denial that the code no longer emits, the README is
lying — so this test runs the actual example through ``run_payload`` and pins
the result to the checked-in golden.  This is the repo's own specimen-at-front
discipline applied to itself: the example IS the README's receipt.

If this breaks, either the schema changed (a version bump, update the golden)
or the example drifted from its prose (fix one of them) — never a casual edit.
"""

from __future__ import annotations

import json
from pathlib import Path

from models import SCHEMA_VERSION
from runner import run_payload

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text())


def test_stale_standing_denied_matches_golden():
    """examples/stale-standing-denied.json → checked-in golden verdict."""
    produced = run_payload(_load("stale-standing-denied.json")).model_dump(mode="json")
    assert produced == _load("stale-standing-denied.verdict.json")


def test_stale_standing_denied_readme_claims():
    """Pin the specific properties the README prose asserts about the specimen,
    so the narrative and the artifact can't diverge silently."""
    v = run_payload(_load("stale-standing-denied.json")).model_dump(mode="json")

    # A credentialed-looking request, denied.
    assert v["status"] == "denied"
    # The denial names the rule (invariant 2: every denial names its rules).
    assert [r["rule_id"] for r in v["failed_rules"]] == ["standing.scope_match"]
    # The aged-out evidence is surfaced, not silently dropped: this is the
    # "it was true when I checked" tell.
    assert len(v["stale_facts"]) == 1
    sf = v["stale_facts"][0]
    assert (sf["source"], sf["claim_state"]) == ("standing:grant-101", "expired")
    # The expired fact did NOT ground the rule (invariant 4: stale cannot
    # produce allowed; here it cannot even satisfy the require).
    assert v["used_facts"] == []


def test_example_golden_schema_version_current():
    """Schema-drift tripwire — same posture as tests/test_golden.py."""
    assert _load("stale-standing-denied.verdict.json")["schema_version"] == SCHEMA_VERSION
