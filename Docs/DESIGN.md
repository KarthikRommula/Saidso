# saidso — design

## The one primitive

A checkpoint between an agent's "call `f(args)`" and the code that runs `f`. It
refuses the call unless every guarded argument traces back to the transcript,
and it keeps a receipt for the ones that pass.

Everything else is packaging around that.

## Module map

| Module | Responsibility |
|---|---|
| `transcript.py` | Append-only, timestamped buffer of `Turn`s (user/agent/system). |
| `normalize.py` | Deterministic normalization: number words, years, dates, phones, text. The make-or-break layer. |
| `_fuzz.py` | Fuzzy match with `rapidfuzz` when present, `difflib` fallback. Zero required deps. |
| `matcher.py` | Per-policy checkers (`SPOKEN`/`CONFIRMED`/`CALLER_ID`/`INFERABLE`) → `GroundingResult` + span. |
| `policy.py` | `Policy` enum + default thresholds. |
| `result.py` | `Span`, `GroundingResult`, `ArgFinding`, `SteerBack` (the block-and-steer contract). |
| `context.py` | `CallContext` + `contextvars` so the decorator reads transcript/metadata implicitly. |
| `attestation.py` | `Attestation` + `AttestationLog` (in-memory + optional JSONL). |
| `grounding.py` | The `@grounded` decorator: bind args → check → block or run + attest. |

## Control flow of a guarded call

```
call f(name=..., dob=...)
   │  (decorator) bind args to names via inspect.signature
   │  resolve CallContext (explicit override > contextvar > empty)
   ▼
for each guarded arg: matcher.check(value, policy, transcript, ctx)
   │
   ├─ any ungrounded ─► build SteerBack(failed, grounded) ─► return it
   │                    (or raise GroundingBlocked if configured)
   │
   └─ all grounded ──► ledger.build(action, findings) ─► run f(...) ─► return
```

## Why deterministic-first

The realtime voice loop has a hard latency ceiling. So matching is:

1. **Normalize** the value and the transcript to the same shape (digits, ISO
   dates, lowercased text).
2. **Exact** (normalized substring) → high confidence.
3. **Fuzzy** (`partial_ratio` ≥ threshold) → medium confidence, with the
   matched turn as the span.

A verifier-model escalation for genuinely ambiguous cases is a roadmap hook,
not on the hot path.

### Dates specifically

Full date parsing of free speech is brittle, so `SPOKEN` for a date passes if
**either** the whole turn parses to the same ISO date **or** all three
components (year, month, day — in digit *or* spoken form) appear in one turn
(`date_components_present`). The component check is the robust workhorse.

## The trust trade-off

This is a **hard firewall**: it can block a legitimate action if the matcher
fails to recognize a real value (a false positive). That is the central risk
and the thing to measure. Thresholds are tunable per policy via
`GroundingConfig`. The steer-back design softens the cost: a wrong block just
makes the agent re-ask, rather than crashing the call.

## Anti-priming (why example values are absent)

Tool descriptions and guard prompts deliberately never contain a placeholder
"bad" value (e.g. a sample DOB). Putting an example value in the prompt teaches
the model to emit it. The future prompt compiler enforces this automatically.
