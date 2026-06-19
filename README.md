# saidso

**A grounding firewall for action-taking AI agents.**

`saidso` sits between an AI agent and its consequential tools (book, transfer,
prescribe, refund, update a record) and **refuses to let the agent commit any
argument that isn't grounded in what the user actually said** — with a
transcript-linked audit trail for every action that does run.

> The name is the whole idea: an action only goes through if the user *said so*.

```python
from saidso import grounded, Policy

@grounded(
    name=Policy.SPOKEN,      # must appear in the caller's speech
    dob=Policy.SPOKEN,       # spoken naturally -> normalized to ISO
    phone=Policy.CALLER_ID,  # comes from carrier metadata, not the mouth
    visit_date=Policy.INFERABLE,  # "tomorrow" -> resolved from the clock
)
def register_patient(name, dob, phone, visit_date): ...
```

## The problem

LLM voice/phone agents don't just talk — they *do things*. To do them, they
call functions:

```python
register_patient(name="John Doe", dob="1990-01-01", ...)
```

Sometimes the model **fills in arguments the caller never said.** Today's
frameworks (LiveKit, Vapi, Pipecat, LangGraph) execute the call anyway — and a
fabricated name or date of birth lands in a real database.

Prompting ("never make up a DOB") is best-effort. It's the *suspect judging
itself*, it leaves no proof, and it silently degrades as you add tools.

`saidso` is the backstop that runs in **code, not in the prompt**: it assumes
the model *will* hallucinate and refuses to let the hallucination cause harm.

## What it does, on every call

1. **Block** — if an argument isn't grounded in the transcript, the function
   body never runs.
2. **Steer back** — instead of a dead error, it returns a structured message
   that makes the agent *re-ask* the caller and try again, in-conversation.
3. **Attest** — for every argument that does go through, it writes a receipt:
   *this value came from these words, at this timestamp, with this confidence.*

```text
agent -> register_patient(name='John Doe', dob='1990-01-01')
BLOCKED: body never ran.
steer-back: "I don't have your name and your date of birth from what the
             caller said. Ask the caller for your name and your date of
             birth, then try again. Do not guess or fill in placeholder values."
```

## The policies

| Policy | A value is grounded if… |
|---|---|
| `Policy.SPOKEN` | it appears in the caller's speech (digits/dates/names normalized, fuzzy-matched) |
| `Policy.CONFIRMED` | the agent read it back **and** the caller affirmed it |
| `Policy.CALLER_ID` | it matches trusted call metadata, not what was spoken |
| `Policy.INFERABLE` | it's derivable from context ("tomorrow" + clock) or was spoken |

## Install

```bash
pip install saidso          # zero required dependencies
pip install saidso[fast]    # add rapidfuzz for faster matching
```

`saidso` works with no third-party packages (stdlib `difflib` fallback) and
uses `rapidfuzz` automatically if it's installed.

## Usage

```python
from saidso import grounded, Policy, Transcript, call_context, AttestationLog

@grounded(name=Policy.SPOKEN, dob=Policy.SPOKEN)
def register_patient(name, dob):
    ...  # your real DB write

# Feed the conversation as it happens:
tr = Transcript()
tr.add_user("Hi, I'd like to book an appointment.")

log = AttestationLog(path="attestations.jsonl")  # optional audit trail

with call_context(tr, ledger=log):
    out = register_patient(name="John Doe", dob="1990-01-01")

if getattr(out, "blocked", False):
    say_to_caller(out.message)   # the agent re-asks; nothing was committed
```

When grounding passes, the body runs normally and an attestation is recorded.
By default a block **returns** a `SteerBack` (so it slots straight into a
tool-use loop); pass `GroundingConfig(raise_on_block=True)` to raise instead.

### Plugging into your agent framework

- **Raw OpenAI / Anthropic tool-use** — return `steer.to_tool_message()` as the
  tool result so the model self-corrects. See
  [`examples/openai_tooluse.py`](examples/openai_tooluse.py).
- **LiveKit / Pipecat / Vapi** — keep a `Transcript` in sync with the
  session's transcription events and open a `call_context`. See
  [`examples/livekit_adapter.py`](examples/livekit_adapter.py).

## Regression harness (CI gate)

Assert that invented values are blocked and real ones commit — turn "we hope it
doesn't fabricate" into a test:

```python
from saidso.testing import GroundingCase

def test_invented_dob_is_blocked():
    (GroundingCase(register_patient)
        .user("Hi, I'd like an appointment")
        .call(name="John Doe", dob="1990-01-01")
        .assert_blocked("name", "dob"))

def test_real_values_commit():
    (GroundingCase(register_patient)
        .user("It's Maria Gomez, born January first nineteen ninety")
        .call(name="Maria Gomez", dob="1990-01-01")
        .assert_grounded())
```

## Production behaviour

- **Fail-closed.** If a grounding check ever raises, the argument is treated as
  ungrounded (blocked) and the error is logged — a crash never opens the gate.
- **Validated at import time.** A policy naming a non-existent parameter raises
  immediately, so a typo can't silently leave a real argument unguarded.
- **No silent over-matching.** Numbers must match as whole values (`"2"` is not
  grounded by `"20"`); short names require exact word matches; `date`, `int`,
  `float`, `bool` arguments are coerced deterministically.
- **Observability.** Blocks and errors log under the `saidso` logger.

Tune thresholds or switch to raising via `GroundingConfig`:

```python
from saidso import GroundingConfig, Policy
cfg = GroundingConfig(thresholds={Policy.SPOKEN: 0.9}, raise_on_block=True)

@grounded(cfg, name=Policy.SPOKEN)
def book(name): ...
```

## Run the demo

```bash
python examples/john_doe_demo.py
```

## Roadmap

The MVP is deterministic-first and intentionally small. Planned next:
verifier-model escalation for ambiguous cases, the **anti-priming prompt
compiler**, the **hallucination regression harness** (pytest-style CI gate),
and first-class framework adapters. See [`Docs/ROADMAP.md`](Docs/ROADMAP.md).

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT — see [`LICENSE`](LICENSE).
