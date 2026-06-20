"""saidso quickstart — writes, reads, and observability in one runnable file.

    python quickstart.py

Shows the whole firewall: ground tool ARGUMENTS against the conversation and prior
tool output (writes), and produce only grounded SPEECH (reads) — with a colored
✓/✗ stream and an end-of-run summary.
"""

from saidso import (
    grounded, grounded_outputs, Policy, from_tool,
    Transcript, ToolLedger, AttestationLog, call_context,
    render_spoken, fact,
    enable_pretty_logging, EventRecorder, summary,
)

# Colored ✓/✗ live stream + remember every decision for the summary at the end.
enable_pretty_logging()
recorder = EventRecorder().attach()


# --- fake backends so this demo runs on its own ---
class _DB:
    def insert(self, given_name, date_of_birth):
        print(f"[db] inserted {given_name} ({date_of_birth})")
        return {"patient_id": "p1"}


class _API:
    def book(self, slot_start):
        print(f"[api] booked {slot_start}")
        return {"ok": True}


db, api = _DB(), _API()


# --- your tools, guarded ---
@grounded(given_name=Policy.SPOKEN, date_of_birth=Policy.SPOKEN)
def register_patient(given_name, date_of_birth):
    return db.insert(given_name, date_of_birth)


@grounded_outputs(slot_start=from_tool("get_slots", "slot_start",
                                       normalize="datetime-minute"))
def book_appointment(slot_start):
    return api.book(slot_start)


# --- one phone call ---
tr = Transcript()
tr.add_user("Hi, I'm Maria, born June 5th 1990.")

ledger = ToolLedger()
ledger.record("get_slots", [
    {"slot_start": "2026-05-22T17:00:00+05:30"},
    {"slot_start": "2026-05-22T09:30:00+05:30"},
])

audit = AttestationLog()

with call_context(tr, ledger=audit, tools=ledger):
    print(register_patient(given_name="Maria", date_of_birth="1990-06-05"))  # ✅ she said both
    print(register_patient(given_name="Bob", date_of_birth="1990-06-05"))    # ❌ "Bob" never said

    print(book_appointment(slot_start="2026-05-22T17:00:00-05:00"))  # ✅ wrong tz -> rewritten
    print(book_appointment(slot_start="2026-05-22T03:00:00+05:30"))  # ❌ never offered

    # what the agent is allowed to SAY (hand the result to your own TTS):
    print(render_spoken("You're set for {time}.", ledger=ledger,
                        time=fact("2026-05-22T17:00:00+05:30",
                                  ("get_slots", "slot_start"))))

print(summary(audit, recorder))
