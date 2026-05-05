"""MCP stdio server exposing the verifier as a single `verify` tool.

Modeled directly on the reference implementation at ~/git/mcp/mcp_ping_server.py.
The decisive transport facts (re-recorded here so this file is self-contained):

- Claude Code's MCP stdio transport uses NDJSON: one JSON object per line,
  terminated by a single \\n.  NOT Content-Length / LSP framing.  If you use
  Content-Length, the server appears to start but tools never appear.  Silent
  failure mode.
- Read with sys.stdin.buffer.readline() (binary, not text).
- Write with sys.stdout.buffer.write(payload + b"\\n") and flush after every write.
- NEVER print to stdout.  All diagnostics go to stderr.  One stray print
  corrupts the transport.
- Echo the client's protocolVersion if supported, else offer your own.
  As of 2026-04, Claude Code requests "2025-03-26".

This server is part of the Governor ecosystem but is not Governor-gated.
The same `run_payload` is used by the library, the CLI, and this MCP tool.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from pydantic import ValidationError

from runner import PayloadError, run_payload

SUPPORTED_PROTOCOL_VERSIONS = ["2025-03-26", "2024-11-05"]
SERVER_NAME = "verifier-mcp"
SERVER_VERSION = "0.1.0"

VERIFY_TOOL = {
    "name": "verify",
    "description": (
        "Verify a proposal against facts and constraint rules. "
        "Returns a Verdict with status (allowed | denied | invalid_input), "
        "failed rules, missing facts, warnings, and contradictions. "
        "A 'denied' verdict is a successful verification — it is not an error."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "proposal": {
                "type": "object",
                "description": "Proposal under evaluation: {action, actor, target, scope}",
            },
            "facts": {
                "type": "array",
                "description": "List of Fact dicts: {subject, field, value, source}",
                "items": {"type": "object"},
            },
            "rules": {
                "type": "array",
                "description": "List of ConstraintRule dicts: {rule_id, description, when, require, severity}",
                "items": {"type": "object"},
            },
        },
        "required": ["proposal", "facts", "rules"],
    },
}


def log(msg: str) -> None:
    """Diagnostics to stderr.  Never stdout — that would corrupt the transport."""
    sys.stderr.write(f"[verifier-mcp pid={os.getpid()}] {msg}\n")
    sys.stderr.flush()


def send(response: dict[str, Any]) -> None:
    body = json.dumps(response, separators=(",", ":"))
    sys.stdout.buffer.write(body.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def read_request() -> dict[str, Any] | None:
    line = sys.stdin.buffer.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return read_request()
    return json.loads(line)


def _ok(rid: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _verify_tool_call(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run the verifier on tool arguments.  Returns an MCP tool result.

    Errors are returned as tool results with isError=true rather than
    JSON-RPC errors, because invalid input is a normal user-facing
    outcome of calling this tool — not a protocol failure.
    """
    try:
        verdict = run_payload(arguments)
    except PayloadError as e:
        return {
            "content": [{"type": "text", "text": f"payload error: {e}"}],
            "isError": True,
        }
    except ValidationError as e:
        return {
            "content": [{"type": "text", "text": f"schema invalid: {e}"}],
            "isError": True,
        }

    return {
        "content": [{"type": "text", "text": verdict.model_dump_json()}],
    }


def dispatch(req: dict[str, Any]) -> dict[str, Any] | None:
    """Pure dispatch — no I/O.  Returns the response dict or None for notifications.

    Split out from the read/send loop so tests can drive it in-process
    without spawning a subprocess or wiring stdio.
    """
    method = req.get("method", "")
    rid = req.get("id")

    if method == "initialize":
        params = req.get("params", {}) or {}
        client_version = params.get("protocolVersion", "")
        negotiated = (
            client_version
            if client_version in SUPPORTED_PROTOCOL_VERSIONS
            else SUPPORTED_PROTOCOL_VERSIONS[0]
        )
        return _ok(rid, {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return _ok(rid, {"tools": [VERIFY_TOOL]})

    if method == "tools/call":
        params = req.get("params", {}) or {}
        name = params.get("name")
        if name != "verify":
            return _err(rid, -32601, f"unknown tool: {name}")
        arguments = params.get("arguments", {}) or {}
        return _ok(rid, _verify_tool_call(arguments))

    return _err(rid, -32601, f"unknown method: {method}")


def main() -> None:
    log("start")
    while True:
        try:
            req = read_request()
        except json.JSONDecodeError as e:
            log(f"json decode error: {e}")
            continue

        if req is None:
            log("eof")
            return

        try:
            resp = dispatch(req)
        except Exception as e:  # noqa: BLE001
            log(f"dispatch error: {type(e).__name__}: {e}")
            resp = _err(req.get("id"), -32603, f"internal error: {e}")

        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
