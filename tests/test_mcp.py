"""In-process MCP dispatch tests.

We do not exercise the stdio transport here — that's already proven by
the reference ping server at ~/git/mcp.  What we test is that the
verifier-mcp dispatch function correctly handles the MCP request shapes
for initialize, tools/list, and tools/call, and routes through the same
run_payload that the library and CLI use.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server import (
    SUPPORTED_PROTOCOL_VERSIONS,
    VERIFY_TOOL,
    dispatch,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_initialize_echoes_known_protocol_version():
    resp = dispatch({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26"},
    })
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2025-03-26"
    assert "tools" in resp["result"]["capabilities"]
    assert resp["result"]["serverInfo"]["name"] == "verifier-mcp"


def test_initialize_falls_back_for_unknown_protocol_version():
    resp = dispatch({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "9999-01-01"},
    })
    assert resp["result"]["protocolVersion"] in SUPPORTED_PROTOCOL_VERSIONS


def test_initialized_notification_returns_none():
    """Notifications get no response — confirmed by None return."""
    assert dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_returns_verify_tool():
    resp = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "verify"
    assert tools[0] == VERIFY_TOOL


@pytest.mark.parametrize("fixture,expected_status", [
    ("allowed.json", "allowed"),
    ("denied.json", "denied"),
    ("invalid.json", "invalid_input"),
])
def test_tools_call_verify_returns_verdict(fixture, expected_status):
    resp = dispatch({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "verify", "arguments": _load(fixture)},
    })
    assert "error" not in resp
    result = resp["result"]
    assert not result.get("isError", False)
    verdict = json.loads(result["content"][0]["text"])
    assert verdict["status"] == expected_status


def test_tools_call_unknown_tool_is_jsonrpc_error():
    resp = dispatch({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_tools_call_bad_payload_is_tool_error_not_protocol_error():
    """Schema/payload errors come back as tool results with isError=true,
    not JSON-RPC errors.  Invalid input is a normal user-facing outcome
    of calling this tool, not a protocol-level failure."""
    resp = dispatch({
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "verify", "arguments": {"proposal": {}}},
    })
    assert "error" not in resp
    result = resp["result"]
    assert result["isError"] is True
    assert "payload" in result["content"][0]["text"] or "schema" in result["content"][0]["text"]


def test_unknown_method_is_jsonrpc_error():
    resp = dispatch({"jsonrpc": "2.0", "id": 6, "method": "frobnicate"})
    assert "error" in resp
    assert resp["error"]["code"] == -32601
