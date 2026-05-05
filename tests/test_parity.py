"""Cross-surface parity.

Library, CLI, and MCP must produce bit-for-bit identical verdict JSON
when given the same payload.  This is the property that makes the
three surfaces actually one component instead of three interfaces in
a trench coat.

If this test fails, one of the wrappers has started doing its own work
on the payload or the verdict — fix the wrapper, do not paper over the
divergence here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from mcp_server import dispatch
from runner import run_payload

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLI = [sys.executable, str(REPO / "cli.py")]


def _via_library(payload: dict) -> str:
    return run_payload(payload).model_dump_json()


def _via_cli(payload: dict) -> str:
    proc = subprocess.run(
        CLI + ["-"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert proc.returncode == 0, f"cli failed: {proc.stderr}"
    return proc.stdout.strip()


def _via_mcp(payload: dict) -> str:
    resp = dispatch({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "verify", "arguments": payload},
    })
    assert "error" not in resp, f"mcp dispatch error: {resp.get('error')}"
    result = resp["result"]
    assert not result.get("isError", False), f"mcp tool error: {result}"
    return result["content"][0]["text"]


@pytest.mark.parametrize("fixture", ["allowed.json", "denied.json", "invalid.json"])
def test_three_surfaces_produce_identical_verdict(fixture):
    payload = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))

    lib = _via_library(payload)
    cli = _via_cli(payload)
    mcp = _via_mcp(payload)

    assert lib == cli, f"library vs CLI diverge:\nlib: {lib}\ncli: {cli}"
    assert lib == mcp, f"library vs MCP diverge:\nlib: {lib}\nmcp: {mcp}"
