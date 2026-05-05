"""Standalone CLI for the verifier.

Usage:
    verifier-check input.json
    cat input.json | verifier-check -

Stdout discipline: only the Verdict JSON.  Diagnostics, parse errors,
and tracebacks all go to stderr.  This matters because the moment a
tool gets piped into something else, one cheerful print to stdout
ruins the party.

Exit codes are semantic, not vibes-based:
    0 — verification ran to completion; verdict printed on stdout
        (this includes "denied" — a denied verdict is a successful run)
    2 — invalid usage or malformed input
    3 — internal error / unexpected exception

Denied verdicts are NOT a nonzero exit; they live in the JSON.  Otherwise
every shell pipeline has to pretend "denied" is a crash.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from runner import PayloadError, run_payload

USAGE = "usage: verifier-check <input.json | ->"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_INTERNAL = 3


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _read_input(arg: str) -> str:
    if arg == "-":
        return sys.stdin.read()
    path = Path(arg)
    if not path.is_file():
        raise PayloadError(f"input file not found: {arg}")
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if len(args) == 1 and args[0] in ("-h", "--help"):
        _eprint(USAGE)
        return EXIT_OK

    if len(args) != 1:
        _eprint(USAGE)
        return EXIT_USAGE

    try:
        raw = _read_input(args[0])
    except PayloadError as e:
        _eprint(f"error: {e}")
        return EXIT_USAGE
    except OSError as e:
        _eprint(f"error: could not read input: {e}")
        return EXIT_USAGE

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        _eprint(f"error: invalid JSON: {e}")
        return EXIT_USAGE

    try:
        verdict = run_payload(payload)
    except PayloadError as e:
        _eprint(f"error: {e}")
        return EXIT_USAGE
    except ValidationError as e:
        _eprint(f"error: payload schema invalid:\n{e}")
        return EXIT_USAGE
    except Exception as e:  # noqa: BLE001 — top-level catchall is the point
        _eprint(f"internal error: {type(e).__name__}: {e}")
        return EXIT_INTERNAL

    sys.stdout.write(verdict.model_dump_json() + "\n")
    sys.stdout.flush()
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
