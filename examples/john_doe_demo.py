"""The core problem saidso solves, in one runnable file.

An LLM agent hallucinates a patient record and writes it to the database.
The same agent behind saidso is blocked, re-asks the caller, and only
commits once the caller provides the data themselves.

Run:
    pip install saidso
    python examples/john_doe_demo.py

No API keys, no network required.
"""

from __future__ import annotations

from saidso import AttestationLog, Policy, SteerBack, Transcript, call_context, grounded

DB: list[dict] = []


@grounded(name=Policy.SPOKEN, dob=Policy.SPOKEN)
def register_patient(name: str, dob: str) -> dict:
    """Write a patient record. Both args must trace to the caller's words."""
    DB.append({"name": name, "dob": dob})
    return {"committed": True, "name": name, "dob": dob}


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def without_saidso() -> None:
    _section("Without saidso")
    tr = Transcript()
    tr.add_user("Hi, I'd like to book an appointment for next week.")
    print('caller: "Hi, I\'d like to book an appointment for next week."')

    # The caller gave no name or DOB. The model invents both.
    name, dob = "John Doe", "1990-01-01"
    DB.append({"name": name, "dob": dob})
    print(f'agent  → register_patient(name={name!r}, dob={dob!r})')
    print(f"result : fabricated record committed → {DB[-1]}")


def with_saidso() -> None:
    DB.clear()
    _section("With saidso — same agent, grounded")
    tr = Transcript()
    tr.add_user("Hi, I'd like to book an appointment for next week.")
    print('caller: "Hi, I\'d like to book an appointment for next week."')

    # Attempt 1: the model hallucinates → blocked before the body runs.
    with call_context(tr):
        result = register_patient(name="John Doe", dob="1990-01-01")

    assert isinstance(result, SteerBack)
    print("agent  → register_patient(name='John Doe', dob='1990-01-01')")
    print(f"saidso → BLOCKED. DB is still {DB!r}")
    print(f"steer  : {result.message!r}")

    # The agent re-asks; the caller provides real data.
    print()
    tr.add_agent("I didn't catch your name and date of birth — could you share them?")
    tr.add_user("Sure — it's Maria Gomez, born January first, nineteen ninety.")
    print('caller: "Sure — it\'s Maria Gomez, born January first, nineteen ninety."')

    # Attempt 2: both args trace to the caller's words → committed and attested.
    log = AttestationLog()
    with call_context(tr, ledger=log, call_id="demo-call-1"):
        result = register_patient(name="Maria Gomez", dob="1990-01-01")

    print("agent  → register_patient(name='Maria Gomez', dob='1990-01-01')")
    print(f"saidso → COMMITTED: {result}")
    print("\nprovenance receipt:")
    for arg in log.records[0].to_dict()["args"]:
        span = arg["span"]
        print(
            f"  {arg['arg']}={arg['value']!r}  "
            f"policy={arg['policy']}  confidence={arg['confidence']:.2f}\n"
            f"    ↳ turn #{span['turn_id']}: \"{span['text']}\""
        )


if __name__ == "__main__":
    without_saidso()
    with_saidso()
    print()
