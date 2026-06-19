"""The John Doe demo: a naked agent invents a patient; saidso blocks it.

Run::

    python examples/john_doe_demo.py

No API keys, no network. This is the 30-second story the project exists for.
"""

from __future__ import annotations

from saidso import AttestationLog, Policy, SteerBack, Transcript, call_context, grounded

# A real action that would touch a database / EHR in production.
DB = []


@grounded(name=Policy.SPOKEN, dob=Policy.SPOKEN)
def register_patient(name, dob):
    DB.append({"name": name, "dob": dob})
    return {"committed": True, "name": name, "dob": dob}


def banner(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def scenario_naked_agent():
    banner("LEFT — naked agent (no firewall)")
    tr = Transcript()
    tr.add_user("Hi, I'd like to book an appointment for next week.")
    print("caller: \"Hi, I'd like to book an appointment for next week.\"")
    # The model hallucinates a name + DOB the caller never gave.
    name, dob = "John Doe", "1990-01-01"
    DB.append({"name": name, "dob": dob})  # straight to the DB
    print(f"agent  -> register_patient(name={name!r}, dob={dob!r})")
    print(f"RESULT : committed fabricated record. DB now: {DB[-1]}")


def scenario_firewalled():
    DB.clear()
    banner("RIGHT — same agent, behind saidso")
    tr = Transcript()
    tr.add_user("Hi, I'd like to book an appointment for next week.")
    print("caller: \"Hi, I'd like to book an appointment for next week.\"")

    with call_context(tr):
        out = register_patient(name="John Doe", dob="1990-01-01")
    assert isinstance(out, SteerBack)
    print("agent  -> register_patient(name='John Doe', dob='1990-01-01')")
    print("BLOCKED: body never ran. DB is still", DB)
    print(f"steer-back to agent: \"{out.message}\"")

    # The agent re-asks; the caller answers; now it's grounded.
    print("\n-- agent re-asks, caller answers --")
    tr.add_agent("I didn't catch your name and date of birth — could you tell me?")
    tr.add_user("Sure, it's Maria Gomez, born January first, nineteen ninety.")
    print("caller: \"Sure, it's Maria Gomez, born January first, nineteen ninety.\"")

    log = AttestationLog()
    with call_context(tr, ledger=log, call_id="call-42"):
        out = register_patient(name="Maria Gomez", dob="1990-01-01")
    print(f"agent  -> register_patient(name='Maria Gomez', dob='1990-01-01')")
    print(f"COMMITTED: {out}")
    print("\nprovenance receipt:")
    for arg in log.records[0].to_dict()["args"]:
        span = arg["span"]
        print(
            f"  - {arg['arg']}={arg['value']!r} via {arg['policy']} "
            f"(conf {arg['confidence']}) grounded by turn #{span['turn_id']}: "
            f"\"{span['text']}\""
        )


if __name__ == "__main__":
    scenario_naked_agent()
    scenario_firewalled()
    print()
