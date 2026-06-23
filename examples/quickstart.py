"""saidso quickstart — writes, provenance, reads, and observability.

Covers the four main patterns in one runnable file:

  1. @grounded         — guard tool args against the conversation transcript
  2. @grounded_outputs — guard args against a specific prior tool's return value
  3. render_spoken     — build a verified spoken line; ungrounded fact raises
  4. EventRecorder     — capture every decision for tests and dashboards

Run:
    pip install saidso
    python examples/quickstart.py

No API keys, no network required.
"""

from __future__ import annotations

from saidso import (
    AttestationLog,
    EventRecorder,
    Policy,
    ToolLedger,
    Transcript,
    call_context,
    enable_pretty_logging,
    fact,
    from_tool,
    grounded,
    grounded_outputs,
    render_spoken,
    summary,
)

# Colored ✓/✗ live stream to stdout; recorder captures every decision.
enable_pretty_logging()
recorder = EventRecorder().attach()


# ── stub backends — no real network needed ────────────────────────────────────

class _PatientDB:
    def insert(self, given_name: str, date_of_birth: str) -> dict:
        print(f"  [db] inserted {given_name!r} ({date_of_birth})")
        return {"patient_id": "p001"}


class _SchedulerAPI:
    def book(self, slot_start: str) -> dict:
        print(f"  [api] booked slot {slot_start!r}")
        return {"booking_id": "b001"}


db = _PatientDB()
api = _SchedulerAPI()


# ── 1. @grounded — args must appear in what the caller said ──────────────────

@grounded(given_name=Policy.SPOKEN, date_of_birth=Policy.SPOKEN)
def register_patient(given_name: str, date_of_birth: str) -> dict:
    return db.insert(given_name, date_of_birth)


# ── 2. @grounded_outputs — args must trace to a specific tool's output ────────

@grounded_outputs(
    slot_start=from_tool("get_slots", "slot_start", normalize="datetime-minute")
)
def book_appointment(slot_start: str) -> dict:
    return api.book(slot_start)


def main() -> None:
    # ── build call state ──────────────────────────────────────────────────────

    tr = Transcript()
    tr.add_user("Hi, I'm Maria, born June 5th 1990.")

    ledger = ToolLedger()
    # Two slots: with >1 candidate there is no single-candidate fallback,
    # so a fabricated timestamp has nothing to match against and is blocked.
    ledger.record("get_slots", [
        {"slot_start": "2026-07-10T09:00:00Z"},
        {"slot_start": "2026-07-10T14:00:00Z"},
    ])

    audit = AttestationLog()

    with call_context(tr, ledger=audit, tools=ledger):

        print("\n── register_patient ──────────────────────────────────────────")

        # ✅ Both args were spoken by the caller.
        print(register_patient(given_name="Maria", date_of_birth="1990-06-05"))

        # ❌ "Bob" never appeared in the transcript → SteerBack (body never runs).
        print(register_patient(given_name="Bob", date_of_birth="1990-06-05"))

        print("\n── book_appointment ──────────────────────────────────────────")

        # ✅ The model passed a different timezone offset for the same instant.
        #    saidso normalizes both sides to minute precision, finds a match,
        #    and rewrites the argument to the canonical value from get_slots.
        print(book_appointment(slot_start="2026-07-10T09:00:00-05:00"))

        # ❌ This timestamp was never offered by get_slots → SteerBack.
        print(book_appointment(slot_start="2026-07-10T03:00:00Z"))

        print("\n── render_spoken ─────────────────────────────────────────────")

        # ✅ The fact traces to a real record in the get_slots ledger.
        #    render_spoken returns the verified string; your TTS speaks it.
        #    saidso never produces audio.
        line = render_spoken(
            "You're booked for {time}.",
            ledger=ledger,
            time=fact("2026-07-10T09:00:00Z", ("get_slots", "slot_start")),
        )
        print(f"  spoken line: {line!r}")

    # ── end-of-call summary ───────────────────────────────────────────────────
    print("\n── summary ───────────────────────────────────────────────────────")
    print(summary(audit, recorder))


if __name__ == "__main__":
    main()
