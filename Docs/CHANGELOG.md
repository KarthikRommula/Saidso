# Changelog

## 0.1.0

First release. A grounding firewall for action-taking agents.

### Core
- `@grounded` decorator: per-argument grounding policies, block-and-steer on
  failure, attestation on success. Sync **and** async tools.
- Policies: `SPOKEN`, `CONFIRMED`, `CALLER_ID`, `INFERABLE`.
- `Transcript` buffer, `call_context` plumbing (contextvars).
- Deterministic matcher with number-word / year / date / phone / text
  normalization. Uses `rapidfuzz` if installed, stdlib `difflib` otherwise
  (zero required dependencies).
- `AttestationLog`: in-memory + optional JSONL provenance ledger.
- `SteerBack` return contract with auto-generated re-ask messages.
- `saidso.testing.GroundingCase`: replay harness for CI gates.

### Production hardening
- **Fail-closed**: a matcher exception blocks the call and logs, never crashes
  or lets it through.
- **Decoration-time validation**: guarding a non-existent parameter raises
  immediately (typos can't leave real args unguarded); unknown policy strings
  and empty policy sets raise.
- **No digit-substring over-matching**: numbers match as whole values only
  (`"2"` is not grounded by `"20"`).
- **No short-string fuzzy over-matching**: tokens shorter than 4 chars require
  exact word matches; multi-token values require every token to match.
- **Type coercion**: `date` / `datetime` / `int` / `float` / `bool` / `Decimal`
  arguments are rendered deterministically before comparison.
- **`CONFIRMED` tolerates filler/backchannel** turns between read-back and the
  caller's "yes".
- **Comma-grouped numbers** (`1,250`) parse correctly.
- `VAR_KEYWORD` (`**kwargs`) functions: guarded args resolved from the kwargs
  dict.
- Observability via the `saidso` logger; `py.typed` ships type information.
