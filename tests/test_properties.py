"""Property tests — invariants that should hold under transformation.

These are the soul-of-the-thing properties paper-Claude flagged from the
Lean kernel side: the verifier is a pure function of {proposal, facts,
rules}.  Order of facts is not part of the meaning of the input.

If any of these break, the verifier has stopped being a function of its
arguments and started having opinions.  That's a regression worth catching.
"""

from __future__ import annotations

import json
import random
from itertools import permutations
from pathlib import Path

import pytest

from runner import run_payload

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", ["allowed.json", "denied.json", "invalid.json"])
def test_status_invariant_under_fact_permutation(fixture):
    """Shuffling the facts list must not change verdict.status.

    The verifier is a function of the *set* of facts, not the sequence.
    Any path-dependence here would mean some hidden state is leaking from
    fact ordering into the verdict — that's not how a logic-level
    admissibility checker is supposed to work.
    """
    payload = _load(fixture)
    baseline_status = run_payload(payload).status

    facts = payload["facts"]
    if len(facts) <= 1:
        pytest.skip("not enough facts to permute")

    if len(facts) <= 5:
        # Exhaustive: try every permutation.
        perms = list(permutations(facts))
    else:
        # Sampled: try a handful of random shuffles.
        rng = random.Random(0xC0FFEE)
        perms = []
        for _ in range(10):
            shuffled = facts[:]
            rng.shuffle(shuffled)
            perms.append(tuple(shuffled))

    for perm in perms:
        permuted = {**payload, "facts": list(perm)}
        assert run_payload(permuted).status == baseline_status, (
            f"verdict status changed under fact permutation: "
            f"baseline={baseline_status} perm={[f.get('source') for f in perm]}"
        )


@pytest.mark.parametrize("fixture", ["allowed.json", "denied.json", "invalid.json"])
def test_status_invariant_under_rule_permutation(fixture):
    """Shuffling the rules list must not change verdict.status either.

    Per-rule checking is independent by design (every failing rule is
    reported, not a minimal subset).  Order of evaluation must be
    irrelevant to the outcome.
    """
    payload = _load(fixture)
    baseline_status = run_payload(payload).status

    rules = payload["rules"]
    if len(rules) <= 1:
        pytest.skip("not enough rules to permute")

    for perm in permutations(rules):
        permuted = {**payload, "rules": list(perm)}
        assert run_payload(permuted).status == baseline_status


RICH_PAYLOAD = {
    "proposal": {
        "action": "deploy",
        "actor": "worker-a",
        "target": "service/api",
        "scope": "prod",
    },
    "facts": [
        {"subject": "actor", "field": "granted_scope", "value": "prod",
         "source": "standing:101"},
        {"subject": "target", "field": "frozen", "value": "true",
         "source": "continuity:f1"},
        {"subject": "target", "field": "freeze_override", "value": "true",
         "source": "continuity:o1"},
        {"subject": "target", "field": "metadata_current", "value": "false",
         "source": "advisory:m1"},
    ],
    "rules": [
        {
            "rule_id": "standing.scope_match",
            "description": "Granted scope must match",
            "kind": "standing",
            "require": [
                {"subject": "actor", "field": "granted_scope", "op": "eq", "value": "prod"}
            ],
        },
        {
            "rule_id": "continuity.freeze_override",
            "description": "Frozen target requires override",
            "kind": "constraint",
            "when": [
                {"subject": "target", "field": "frozen", "op": "eq", "value": "true"}
            ],
            "require": [
                {"subject": "target", "field": "freeze_override", "op": "eq", "value": "true"}
            ],
        },
        {
            "rule_id": "advisory.metadata",
            "description": "Metadata should be current",
            "kind": "constraint",
            "require": [
                {"subject": "target", "field": "metadata_current", "op": "eq", "value": "true"}
            ],
            "severity": "warn",
        },
    ],
}


def test_rich_payload_status_invariant_under_fact_permutation():
    """Rich case (4 facts, 3 rules of mixed kinds and severities) actually
    exercises the permutation invariant — the canonical fixtures are too
    small to be meaningful here."""
    baseline = run_payload(RICH_PAYLOAD).status

    for perm in permutations(RICH_PAYLOAD["facts"]):
        permuted = {**RICH_PAYLOAD, "facts": list(perm)}
        assert run_payload(permuted).status == baseline


def test_rich_payload_status_invariant_under_rule_permutation():
    baseline = run_payload(RICH_PAYLOAD).status

    for perm in permutations(RICH_PAYLOAD["rules"]):
        permuted = {**RICH_PAYLOAD, "rules": list(perm)}
        assert run_payload(permuted).status == baseline


@pytest.mark.parametrize("fixture", ["allowed.json", "denied.json", "invalid.json"])
def test_run_payload_is_deterministic(fixture):
    """Two runs of the same payload produce identical verdict JSON.

    This is the trivial form of paper-Claude's observation-equivalence
    note — verdict is a pure function of input.  Worth pinning explicitly:
    if Z3 ever introduces nondeterminism in our usage, we want to know.
    """
    payload = _load(fixture)
    a = run_payload(payload).model_dump_json()
    b = run_payload(payload).model_dump_json()
    assert a == b
