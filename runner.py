"""Single dispatch entry point shared by every surface.

Library, CLI, and MCP server all funnel through `run_payload`.
One truth, three wrappers — so a verdict produced by the library is
bit-for-bit the same as one produced by the CLI or MCP tool.

The verifier is part of the Governor ecosystem, but it is not
Governor-gated.  It can be used directly as a Python library,
a standalone CLI, or an MCP tool.
"""

from __future__ import annotations

from typing import Any

from models import ConstraintRule, Fact, Proposal, Verdict
from verifier import verify


class PayloadError(ValueError):
    """The combined payload was missing a top-level key or had the wrong shape.

    Distinct from a Pydantic ValidationError on a child model: this fires
    before any field-level parsing, so callers can map it cleanly to a
    usage / 400-class error rather than an internal failure.
    """


_REQUIRED_KEYS = ("proposal", "facts", "rules")


def run_payload(payload: Any) -> Verdict:
    """Verify a combined payload dict and return a Verdict.

    Expected shape:
        {
            "proposal": {...},   # one Proposal
            "facts":    [...],   # list of Fact dicts
            "rules":    [...]    # list of ConstraintRule dicts
        }

    Raises PayloadError if the top-level shape is wrong.  Pydantic
    ValidationError propagates for malformed children — callers decide
    whether to treat that as usage error or internal error.
    """
    if not isinstance(payload, dict):
        raise PayloadError(f"payload must be a JSON object, got {type(payload).__name__}")

    missing = [k for k in _REQUIRED_KEYS if k not in payload]
    if missing:
        raise PayloadError(f"payload missing required keys: {missing}")

    if not isinstance(payload["facts"], list):
        raise PayloadError("'facts' must be a list")
    if not isinstance(payload["rules"], list):
        raise PayloadError("'rules' must be a list")

    proposal = Proposal.model_validate(payload["proposal"])
    facts = [Fact.model_validate(f) for f in payload["facts"]]
    rules = [ConstraintRule.model_validate(r) for r in payload["rules"]]

    return verify(proposal, facts, rules)
