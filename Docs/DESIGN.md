# Design notes

Internal design rationale for contributors. For the public API reference see
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## The core primitive

A checkpoint between an agent's "call `f(args)`" and the code that actually
runs `f`. The checkpoint refuses the call unless every guarded argument traces
back to the transcript or the tool ledger. Every argument that passes gets a
receipt.

Everything else in the library is packaging around that single primitive.

---

## Control flow of a guarded call

```
call f(name=..., dob=...)
   │
   │  decorator: bind args via inspect.signature
   │  resolve CallContext (explicit > contextvar > empty)
   ▼
for each guarded arg:
   matcher.check(value, policy, transcript, ctx) → GroundingResult
   │
   ├─ any ungrounded ──► SteerBack(failed=[...], grounded=[...])
   │                     returned to caller; body never runs
   │                     (or GroundingBlocked raised if configured)
   │
   └─ all grounded ────► rewrite each arg to its canonical value
                         run f(canonical_args)
                         write Attestation to ledger
                         return result
```

`@grounded_outputs` follows the same shape but runs `reconcile()` against the
`ToolLedger` instead of the transcript.

---

## Matching strategy

The realtime voice loop has a hard latency ceiling, so matching is deterministic
and staged — no model call on the hot path.

**Step 1 — normalize.** Both the argument value and every transcript turn are
passed through the same normalizer (number-words → digits, ISO dates, E.164
phones, lowercase). This is the make-or-break layer: most false blocks in
production trace to missing normalization coverage, not wrong thresholds.

**Step 2 — exact substring.** The normalized value is searched as a substring
of the normalized turn text. On a hit the confidence is 1.0.

**Step 3 — fuzzy.** `partial_ratio` (via `rapidfuzz` or `difflib`) against each
turn. Confidence equals the normalized score. Passes if ≥ the policy threshold.

Thresholds are tunable per argument via `Policy.SPOKEN(threshold=0.85)` or
globally via `GroundingConfig`.

### Date matching

Full date parsing of free speech is brittle. `SPOKEN` for a date passes if
**either** the full turn parses to the same ISO date **or** all three components
(year, month, day — digit or spoken form) appear within a single turn. The
component check is the robust workhorse; the full-parse path is a fast exit for
clean input.

---

## The steer-back contract

A block is not an error — it is an expected, recoverable state. The `SteerBack`
return value carries:

- `failed` — the argument names that did not ground.
- `grounded` — the argument names that did.
- `message` — a caller-facing re-ask the agent can speak verbatim.

`raise_on_block=True` switches to exception mode for callers that prefer it.
`steer_style="spoken"` generates a natural-language re-ask free of technical
jargon, suitable for direct TTS.

---

## Shadow mode

`GroundingConfig(enforce=False)` records every would-block to the
`AttestationLog` with `status="shadow_block"` without actually blocking the
call. Use this to calibrate policy thresholds on real traffic before enforcing.
The shadow log has the same schema as a live log; analysis tooling works on
both.

---

## The trust trade-off

saidso is a **hard firewall**. It can block a legitimate action if the matcher
fails to recognize a value that is genuinely present in the transcript (a false
block). That is the central operational risk.

The steer-back design bounds the cost: a false block makes the agent re-ask once,
rather than failing the call. Thresholds and normalizers let operators tune
precision/recall per deployment.

The alternative — only blocking obvious hallucinations while letting ambiguous
cases through — is not a safe default for a library whose job is to prevent
committed fabrications. The default posture is strict; operators loosen it
deliberately with evidence.

---

## Anti-priming

Tool descriptions and guard prompts deliberately never contain a placeholder
"bad" value (e.g. a sample DOB). Placing an example value in the prompt teaches
the model to emit it. The ROADMAP item for a prompt compiler enforces this
constraint automatically from function signatures.

---

## Why zero required dependencies

A grounding firewall must be deployable everywhere an agent runs. Adding a
required C extension (like `rapidfuzz`) would break pure-Python and
restricted-environment deployments. The `difflib` fallback is ~10% slower on
fuzzy matching but produces identical verdicts. Install `saidso[fast]` to
get `rapidfuzz` when throughput matters.
