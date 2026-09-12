# Verifier HOWTO

Choose Verifier for a bounded check of a caller-encoded proposal, supplied facts,
and supplied rules. It is optional: use it when that exact check is useful, not
as a mandatory formalization step for every task. It does not fetch facts, decide
whether the world is true, select policy, or authorize action.

## CLI

Install this checkout, then run one of the public fixtures:

```sh
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
verifier-check tests/fixtures/allowed.json
verifier-check tests/fixtures/denied.json
verifier-check tests/fixtures/invalid.json
```

Each completed verifier result prints JSON and exits `0`, including `denied` and
`invalid_input`; inspect `status` rather than treating a zero exit as approval.
Malformed JSON or command usage exits `2`. An unexpected internal failure exits
`3`.

## Stdio MCP

Run the installed `verifier-mcp` executable as an NDJSON stdio server. It exposes
one tool, `verify`, whose arguments are the same `{proposal, facts, rules}` object
used by the CLI. A malformed tool payload is returned as an MCP tool error; it is
not a successful verification verdict.

## Interpret results narrowly

The wire statuses are `allowed`, `advisory`, `denied`, and `invalid_input`.
`allowed` says only that the supplied current facts satisfied the supplied encoded
rules. It does not authenticate sources, establish truth, or grant authority.
Expired, revoked, and stale referenced facts cannot ground a rule; the result may
report them as `stale_facts`.

There is no configured solver timeout and no typed timeout, translation-failure,
or solver-unknown result on this surface. Do not rely on it for those distinctions
or present it as a complete formal-methods service.
