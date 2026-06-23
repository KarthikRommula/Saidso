# Architecture

saidso is a grounding firewall for action-taking AI agents. It enforces one rule:
**nothing is committed (a tool argument) or spoken (a fact) unless it traces back
to something real — what the user said, or what a tool returned.** Anything
ungrounded is blocked before it can cause harm.

---

## The two surfaces

An agent can lie in exactly two places. saidso defends both.

| The agent lies about… | Example failure | saidso defense |
|---|---|---|
| **What it does** — a tool argument | books a slot that was never offered | `@grounded` / `@grounded_outputs` |
| **What it says** — a spoken fact | "booked with Dr. House" (no such doctor) | `render_spoken` / `reconcile_turn` |

The first surface is fail-closed by interception: the tool body never runs if an
argument is ungrounded. The second surface is fail-closed by construction:
`render_spoken` assembles the spoken line only from verified facts and raises
`UngroundedSpeech` if any fact cannot be grounded.

---

## Package layout

```
saidso/
├── __init__.py          Public API — everything below is re-exported here
│
├── policy.py            Policy enum and per-policy confidence thresholds
├── transcript.py        Transcript, Turn — the per-call conversation buffer
├── context.py           CallContext, call_context() — contextvars-based call scope
├── result.py            GroundingResult, ArgFinding, SteerBack, Span — verdicts
├── attestation.py       Attestation, AttestationLog — the pass audit trail
│
├── grounding.py         @grounded — ground args against the CONVERSATION
├── provenance.py        @grounded_outputs, from_tool, ToolLedger — ground args
│                        against TOOL OUTPUT; reconcile, Resolution, Status
│
├── speech/
│   ├── render.py        render_spoken, fact — deterministic grounded speech
│   ├── reconcile.py     reconcile_turn, ClaimPattern — turn-level claim auditing
│   └── monitor.py       find_ungrounded_names — best-effort name detection
│
├── observe.py           enable_pretty_logging, EventRecorder, summary
├── testing.py           GroundingCase — pytest-style replay harness
│
└── _matching/           (private) fuzzy-matching engine
    ├── matcher.py        Per-policy checkers → GroundingResult
    ├── normalize.py      Number-word, date, phone, and text normalization
    ├── fuzz.py           rapidfuzz with stdlib difflib fallback
    └── locale.py         EN / ES locale packs
```

---

## Public API reference

### Decorators

| Name | Grounds against | Behavior on failure |
|---|---|---|
| `@grounded(arg=Policy.X)` | The conversation transcript | Returns `SteerBack`; body never runs |
| `@grounded_outputs(arg=from_tool(...))` | A specific prior tool's return value | Returns `SteerBack`; body never runs |

Both decorators work on sync and async functions, with positional and keyword
arguments. A passing argument is rewritten to its **canonical value** (the exact
string the tool returned or the caller spoke), not the value the model passed in.

### Policies

Policies apply to `@grounded`. Each specifies what evidence is required for an
argument to pass.

| Policy | An argument is grounded if… |
|---|---|
| `Policy.SPOKEN` | It appears in the caller's transcript (normalized + fuzzy-matched) |
| `Policy.CONFIRMED` | The agent read it back **and** the caller affirmed it |
| `Policy.CALLER_ID` | It matches trusted call metadata (not the model's output) |
| `Policy.INFERABLE` | It is derivable from context ("tomorrow" + clock) or was spoken |

Fine-tune per argument with `Policy.SPOKEN(normalize="spelled-name", threshold=0.85)`.

### Provenance

Provenance applies to `@grounded_outputs`. It grounds tool arguments against what
an earlier read tool actually returned.

| Symbol | Role |
|---|---|
| `ToolLedger` | Accumulates what each read tool returned this call (`record`, `candidates`) |
| `from_tool(tool, key, normalize=...)` | Declares that an argument must originate from a named tool's output |
| `reconcile(value, candidates, ...)` | The judge: exact → normalized → single-candidate → block |
| `Resolution` / `Status` | Verdict object + status enum (`PASS_EXACT`, `BLOCK_NO_MATCH`, …) |

Built-in normalizers: `exact`, `casefold`, `e164`, `datetime-minute`, `money`.

### Reads (`saidso.speech`)

The reads surface guards what the agent says aloud.

| Symbol | Role |
|---|---|
| `render_spoken(template, ledger=..., **facts)` | Builds a verified spoken line; raises `UngroundedSpeech` if any fact fails |
| `fact(value, *sources, render=...)` | One interpolated slot + its provenance + an optional formatter |
| `try_render_spoken(...)` | Same as `render_spoken` but returns `None` instead of raising |
| `reconcile_turn(agent_text, attestations=..., claim_patterns=...)` | Flags spoken completion claims not backed by a successful write |
| `find_ungrounded_names(...)` | Best-effort post-turn detector for names not in the ground-truth set |
| `attest_action(name, ...)` | Records an argument-less action (`end_call`, `transfer_to_human`) |

`render_spoken` returns the verified **string**. saidso is TTS-agnostic and never
produces audio.

### Core types and scope

| Symbol | Role |
|---|---|
| `Transcript` / `Turn` | The conversation buffer (`add_user`, `add_agent`, `add_system`) |
| `call_context(transcript, ledger=..., tools=..., metadata=...)` | Opens a call scope so decorators find what they need (contextvars; async-safe) |
| `SteerBack` | The block-and-steer result: `.message`, `.failed`, `.grounded` |
| `Attestation` / `AttestationLog` | A receipt per passing action; optional JSONL audit trail |
| `GroundingConfig` | Per-decorator tuning: `raise_on_block`, `enforce` (shadow mode), `steer_style` |

### Observability

| Symbol | Role |
|---|---|
| `enable_pretty_logging()` | Colored ✓/✗ live stream to stdout (auto-disabled when not a TTY) |
| `EventRecorder` | Captures the structured event stream (`.passed`, `.blocked`) |
| `summary(audit, recorder)` | End-of-call counts and one row per decision |

Every decision emits a structured log event on the `saidso` logger with keys
`saidso_event` (`pass` / `block`), `saidso_action`, and `saidso_args`.

### Testing

```python
from saidso.testing import GroundingCase

def test_invented_dob_is_blocked():
    (GroundingCase(register_patient)
        .user("Hi, I'd like an appointment")
        .call(name="John Doe", dob="1990-01-01")
        .assert_blocked("name", "dob"))
```

`GroundingCase` builds a transcript, opens a call context, and provides
`assert_blocked` / `assert_grounded` / `assert_rewritten` assertions.

---

## Design principles

**Fail-closed.** Any exception inside a grounding check is treated as a block,
not a pass. A broken metal detector locks the door.

**Deterministic and fast.** Pure Python, in-process. A write check is ~12 µs —
roughly 1/2000th of a single backend round-trip.

**Zero required dependencies.** `rapidfuzz` is used when installed
(`pip install saidso[fast]`); stdlib `difflib` is the fallback. Ships `py.typed`.

**Model- and platform-agnostic.** No model SDK is imported. saidso operates on
text, function arguments, and recorded tool outputs — primitives every stack exposes.

**Validated at import time.** A `@grounded` policy naming a non-existent
parameter raises immediately on decoration, not at runtime.
