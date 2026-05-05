"""End-to-end CLI tests via subprocess.

Validates the contract that matters most:
- Stdout contains only JSON.
- Diagnostics go to stderr.
- Exit codes are semantic (0 = ran, 2 = usage, 3 = internal).
- A 'denied' verdict is exit 0 — denial is a successful run, not a crash.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLI = [sys.executable, str(REPO / "cli.py")]


def _run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + args,
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO,
    )


@pytest.mark.parametrize("fixture,expected_status", [
    ("allowed.json", "allowed"),
    ("denied.json", "denied"),
    ("invalid.json", "invalid_input"),
])
def test_cli_fixture_round_trip(fixture, expected_status):
    proc = _run([str(FIXTURES / fixture)])

    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    assert proc.stderr == "", "stderr must be empty on success"

    verdict = json.loads(proc.stdout)
    assert verdict["status"] == expected_status


def test_cli_denied_is_exit_zero():
    """A denied verdict is a successful run.  Pipelines must not have to
    pretend denial is a crash."""
    proc = _run([str(FIXTURES / "denied.json")])
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "denied"


def test_cli_stdin_dash():
    payload = (FIXTURES / "allowed.json").read_text()
    proc = _run(["-"], stdin=payload)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "allowed"


def test_cli_missing_file_is_usage_error():
    proc = _run(["/nonexistent/path.json"])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "not found" in proc.stderr


def test_cli_invalid_json_is_usage_error():
    proc = _run(["-"], stdin="not json{")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "invalid JSON" in proc.stderr


def test_cli_no_args_is_usage_error():
    proc = _run([])
    assert proc.returncode == 2
    assert "usage:" in proc.stderr


def test_cli_help_is_exit_zero():
    proc = _run(["--help"])
    assert proc.returncode == 0
    assert "usage:" in proc.stderr


def test_cli_stdout_is_only_json():
    """No leading banners, no trailing logs.  Just one line of JSON."""
    proc = _run([str(FIXTURES / "allowed.json")])
    assert proc.returncode == 0
    lines = [l for l in proc.stdout.split("\n") if l]
    assert len(lines) == 1
    json.loads(lines[0])  # parses cleanly
