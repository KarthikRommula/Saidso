"""Adversarial proof for tool-output provenance grounding (saidso #1).

Two safety invariants are asserted exhaustively:

  (I)  no false-accept  — a PASS never forwards a value that isn't a real
       candidate the tool returned (canonical is always in the candidate set);
  (II) no false-reject  — an exact or uniquely-normalized value always passes.

Plus the realistic LiveKit shapes (slot_start tz-reconstruction, opaque ids)
and the decorator end-to-end (block returns SteerBack + body never runs; pass
rewrites the arg to the canonical tool value).
"""

from __future__ import annotations

import pytest

from saidso import (
    AttestationLog,
    SteerBack,
    ToolLedger,
    call_context,
    from_tool,
    grounded_outputs,
    reconcile,
)
from saidso.provenance import Status

# --------------------------------------------------------------------------- #
# Engine — exact / normalized / fallback / block matrix
# --------------------------------------------------------------------------- #

IDS = ["dr_a1b2", "dr_c3d4", "dr_e5f6"]
SLOTS = ["2026-05-22T09:30:00+05:30", "2026-05-22T17:00:00+05:30"]


def test_raw_exact_id_passes():
    r = reconcile("dr_c3d4", IDS)
    assert r.status is Status.PASS_EXACT
    assert r.canonical == "dr_c3d4"


def test_string_drift_exact_passes():
    # model returns int 5, candidate is "5"
    r = reconcile(5, ["5", "7", "9"])
    assert r.passed and r.canonical == "5"


def test_datetime_reconstructed_offset_passes_to_canonical():
    # model rebuilt the timestamp with the wrong tz offset
    r = reconcile("2026-05-22T17:00:00-05:00", SLOTS, normalize="datetime-minute")
    assert r.status is Status.PASS_NORMALIZED
    assert r.canonical == "2026-05-22T17:00:00+05:30"  # the real slot


def test_datetime_seconds_drift_passes():
    r = reconcile("2026-05-22T17:00:45+05:30", SLOTS, normalize="datetime-minute")
    assert r.passed and r.canonical == "2026-05-22T17:00:00+05:30"


def test_e164_normalized_passes():
    r = reconcile("+1 (512) 248-8888", ["+15122488888"], normalize="e164")
    assert r.passed and r.canonical == "+15122488888"


def test_casefold_normalized_passes():
    r = reconcile("GOMEZ", ["Gomez", "Smith"], normalize="casefold")
    assert r.passed and r.canonical == "Gomez"


def test_money_normalized_passes():
    r = reconcile("$1,200", ["1200.00", "950.00"], normalize="money")
    assert r.passed and r.canonical == "1200.00"


def test_exact_beats_ambiguous():
    # value equals one raw candidate exactly, even though another normalizes the same
    r = reconcile("Gomez", ["Gomez", "gomez"], normalize="casefold")
    assert r.status is Status.PASS_EXACT and r.canonical == "Gomez"


def test_single_candidate_fallback_passes():
    r = reconcile("garbage_id", ["the_only_doctor"])
    assert r.status is Status.PASS_SINGLE and r.canonical == "the_only_doctor"


def test_single_candidate_can_be_disabled():
    r = reconcile("garbage_id", ["the_only_doctor"], allow_single_candidate=False)
    assert not r.passed and r.status is Status.BLOCK_NO_MATCH


# --------------------------- blocks (fail-closed) -------------------------- #


def test_ambiguous_two_same_minute_blocks():
    cands = ["2026-05-22T17:00:00+05:30", "2026-05-22T17:00:00-08:00"]  # same wall minute
    r = reconcile("2026-05-22T17:00:00+00:00", cands, normalize="datetime-minute")
    assert r.status is Status.BLOCK_AMBIGUOUS and r.canonical is None


def test_fabricated_value_blocks_when_multiple_candidates():
    r = reconcile("2026-05-22T13:15:00+05:30", SLOTS, normalize="datetime-minute")
    assert r.status is Status.BLOCK_NO_MATCH and r.canonical is None


def test_no_candidates_blocks():
    r = reconcile("dr_c3d4", [])  # lookup tool never ran
    assert r.status is Status.BLOCK_NO_CANDIDATES


@pytest.mark.parametrize("bad", [None, "", "   "])
def test_empty_value_blocks(bad):
    r = reconcile(bad, IDS)
    assert r.status is Status.BLOCK_NO_VALUE


# --------------------------------------------------------------------------- #
# Invariants — the 100% claims, swept over an adversarial matrix
# --------------------------------------------------------------------------- #

_SWEEP_CANDS = ["2026-05-22T09:30:00+05:30", "2026-05-22T17:00:00+05:30",
                "2026-05-23T11:00:00+05:30"]
_SWEEP_VALUES = [
    "2026-05-22T09:30:00+05:30",   # exact
    "2026-05-22T17:00:00-05:00",   # reconstructed offset -> unique
    "2026-05-23T11:00:59+00:00",   # seconds+offset drift -> unique
    "2026-05-22T13:15:00+05:30",   # fabricated -> block
    "2026-05-24T08:00:00+05:30",   # fabricated -> block
    "not-a-timestamp",             # garbage -> block
    "",                            # empty -> block
]


@pytest.mark.parametrize("value", _SWEEP_VALUES)
def test_invariant_no_false_accept(value):
    """(I) Every PASS forwards a canonical that is genuinely a candidate."""
    r = reconcile(value, _SWEEP_CANDS, normalize="datetime-minute",
                  allow_single_candidate=False)
    if r.passed:
        assert r.canonical in _SWEEP_CANDS


def test_invariant_no_false_reject():
    """(II) Exact and uniquely-normalized values always pass to the right slot."""
    assert reconcile("2026-05-22T09:30:00+05:30", _SWEEP_CANDS,
                     normalize="datetime-minute").canonical == _SWEEP_CANDS[0]
    assert reconcile("2026-05-22T17:00:00-05:00", _SWEEP_CANDS,
                     normalize="datetime-minute").canonical == _SWEEP_CANDS[1]
    assert reconcile("2026-05-23T11:00:59+00:00", _SWEEP_CANDS,
                     normalize="datetime-minute").canonical == _SWEEP_CANDS[2]


# --------------------------------------------------------------------------- #
# Decorator end-to-end — the real book/reschedule shapes
# --------------------------------------------------------------------------- #


def _book_factory(sink):
    @grounded_outputs(
        slot_start=from_tool("get_slots", "slot_start", normalize="datetime-minute"),
    )
    async def book_appointment(context, slot_start):
        sink.append(slot_start)
        return {"booked": True, "slot_start": slot_start}

    return book_appointment


async def test_book_reconstructed_slot_passes_and_rewrites():
    sink: list = []
    book = _book_factory(sink)
    ledger = ToolLedger()
    ledger.record("get_slots", [
        {"slot_start": "2026-05-22T09:30:00+05:30"},
        {"slot_start": "2026-05-22T17:00:00+05:30"},
    ])
    log = AttestationLog()
    with call_context(tools=ledger, ledger=log, call_id="c1"):
        result = await book(None, slot_start="2026-05-22T17:00:00-05:00")  # rebuilt tz
    assert result["booked"] is True
    # body received the CANONICAL slot, not the model's reconstructed string
    assert sink == ["2026-05-22T17:00:00+05:30"]
    assert result["slot_start"] == "2026-05-22T17:00:00+05:30"
    assert len(log) == 1  # attestation recorded


async def test_book_fabricated_slot_blocks_and_body_never_runs():
    sink: list = []
    book = _book_factory(sink)
    ledger = ToolLedger()
    ledger.record("get_slots", [
        {"slot_start": "2026-05-22T09:30:00+05:30"},
        {"slot_start": "2026-05-22T17:00:00+05:30"},
    ])
    with call_context(tools=ledger):
        outcome = await book(None, slot_start="2026-05-22T13:15:00+05:30")  # never offered
    assert isinstance(outcome, SteerBack)
    assert outcome.blocked is True
    assert sink == []  # body never ran — nothing booked


async def test_book_with_no_lookup_blocks():
    sink: list = []
    book = _book_factory(sink)
    with call_context(tools=ToolLedger()):  # get_slots never called
        outcome = await book(None, slot_start="2026-05-22T17:00:00+05:30")
    assert isinstance(outcome, SteerBack)
    assert sink == []


async def test_reschedule_two_provenance_args():
    sink: list = []

    @grounded_outputs(
        appointment_id=from_tool("list_appointments", "appointment_id"),
        slot_start=from_tool("get_slots", "slot_start", normalize="datetime-minute"),
    )
    async def reschedule(context, appointment_id, slot_start):
        sink.append((appointment_id, slot_start))
        return {"ok": True}

    ledger = ToolLedger()
    # two appointments on file, so a fabricated id matches none (no single fallback)
    ledger.record("list_appointments", [
        {"appointment_id": "appt_777"}, {"appointment_id": "appt_888"},
    ])
    ledger.record("get_slots", [{"slot_start": "2026-06-01T10:00:00+05:30"}])
    with call_context(tools=ledger):
        # right appointment, reconstructed slot time
        ok = await reschedule(None, appointment_id="appt_777",
                              slot_start="2026-06-01T10:00:00Z")
        # fabricated appointment id -> block
        bad = await reschedule(None, appointment_id="appt_000",
                               slot_start="2026-06-01T10:00:00+05:30")
    assert ok == {"ok": True}
    assert sink == [("appt_777", "2026-06-01T10:00:00+05:30")]  # both canonical
    assert isinstance(bad, SteerBack)


async def test_multi_source_accepts_either_tool():
    sink: list = []

    @grounded_outputs(
        doctor_id=from_tool(("list_doctors", "doctor_id"),
                            ("list_appointments", "doctor_id")),
    )
    async def get_slots(context, doctor_id):
        sink.append(doctor_id)
        return {"ok": True}

    ledger = ToolLedger()
    ledger.record("list_doctors", [{"doctor_id": "dr_fresh"}])
    ledger.record("list_appointments", [{"doctor_id": "dr_existing"}])
    with call_context(tools=ledger):
        a = await get_slots(None, doctor_id="dr_existing")  # from an appointment
        b = await get_slots(None, doctor_id="dr_fresh")     # from the doctor list
        bad = await get_slots(None, doctor_id="dr_invented")  # neither -> block
    assert a == {"ok": True} and b == {"ok": True}
    assert sink == ["dr_existing", "dr_fresh"]
    assert isinstance(bad, SteerBack)


def test_typo_in_spec_raises_at_decoration():
    with pytest.raises(ValueError):
        @grounded_outputs(bogus_arg=from_tool("get_slots", "slot_start"))
        async def book(context, slot_start):  # no 'bogus_arg' param
            return None
