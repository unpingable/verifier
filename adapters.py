"""Adapters: domain objects → verifier Facts.

Each adapter translates one upstream system's state into the verifier's
typed IR.  The verifier never imports domain internals — it only sees
what these adapters produce.

Standing is Rust; we consume its JSON serialization.
Continuity is Python; we consume MemoryObject directly.
"""

from __future__ import annotations

from typing import Any

from models import ConstraintRule, ConstraintAtom, Fact, Proposal


# ------------------------------------------------------------------
# Standing → Facts
# ------------------------------------------------------------------

def standing_grant_to_facts(grant: dict[str, Any]) -> list[Fact]:
    """Convert a Standing grant (JSON dict) into verifier Facts.

    Expected shape (from standing-grant crate serialization):
        {
            "id": "...",
            "subject": {"id": "...", "label": "..."},
            "scope": {"action": "...", "target": "..."},
            "issued_at": "...",
            "expires_at": "..."
        }
    """
    subject_id = grant["subject"]["id"]
    scope = grant["scope"]
    grant_id = grant["id"]
    source = f"standing:grant-{grant_id}"

    return [
        Fact(
            subject="actor",
            field="granted_scope",
            value=scope["action"],
            source=source,
        ),
        Fact(
            subject="actor",
            field="granted_target",
            value=scope["target"],
            source=source,
        ),
        Fact(
            subject="actor",
            field="principal_id",
            value=subject_id,
            source=source,
        ),
    ]


# ------------------------------------------------------------------
# Continuity → Facts
# ------------------------------------------------------------------

def memory_to_facts(memory: dict[str, Any]) -> list[Fact]:
    """Convert a Continuity MemoryObject (as dict) into verifier Facts.

    Extracts facts from the content dict.  Each key/value in content
    becomes a Fact with subject derived from scope and kind.

    Only COMMITTED memories with ACTIONABLE reliance class produce
    facts the verifier should treat as ground truth.  Other memories
    are returned with their actual status/reliance so the caller
    can decide, but the verifier's closed-world assumption means
    non-actionable facts won't satisfy rules that expect them.
    """
    memory_id = memory["memory_id"]
    scope = memory["scope"]
    kind = memory["kind"]
    content = memory.get("content", {})
    source = f"continuity:{memory_id}"

    facts: list[Fact] = []

    # Memory metadata as facts
    facts.append(Fact(
        subject="target",
        field=f"{kind}_status",
        value=memory["status"],
        source=source,
    ))

    facts.append(Fact(
        subject="target",
        field=f"{kind}_reliance",
        value=memory.get("reliance_class", "none"),
        source=source,
    ))

    # Content fields as facts
    for key, value in content.items():
        if isinstance(value, (str, int, bool)):
            facts.append(Fact(
                subject="target",
                field=key,
                value=value,
                source=source,
            ))

    return facts


# ------------------------------------------------------------------
# Proposal construction
# ------------------------------------------------------------------

def make_proposal(
    action: str,
    actor_principal_id: str,
    target: str,
    scope: str,
) -> Proposal:
    """Build a Proposal from domain values."""
    return Proposal(
        action=action,
        actor=actor_principal_id,
        target=target,
        scope=scope,
    )
