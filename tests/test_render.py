"""Reads guarantee: deterministic grounded speech (saidso.speech.render).

These prove the "100% reads" claim WITHOUT any TTS or audio — the guarantee is about
which string is allowed to be produced. Every dynamic fact in a rendered line must
trace to real tool output; a fabricated fact yields no line at all (fail-closed).
"""

from __future__ import annotations

import pytest

from saidso import (
    ToolLedger,
    UngroundedSpeech,
    call_context,
    fact,
    render_spoken,
    try_render_spoken,
)


# A deterministic renderer: ISO timestamp -> wall-clock "5:00 PM" (offset-agnostic).
def to_clock(iso: str) -> str:
    hm = iso[11:16]
    hour, minute = int(hm[:2]), hm[3:5]
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute} {suffix}"


SLOT = "2026-05-22T17:00:00+05:30"


def _ledger() -> ToolLedger:
    led = ToolLedger()
    led.record("list_doctors", [{"doctor_id": "dr1", "doctor_name": "Dr. Rashmi Indrakanti"}])
    led.record("get_slots", [
        {"slot_start": SLOT},
        {"slot_start": "2026-05-22T09:30:00+05:30"},
    ])
    return led


# ------------------------------- pass paths ------------------------------- #


def test_all_facts_grounded_renders_line():
    line = render_spoken(
        "You're booked with {doctor} at {time}.",
        ledger=_ledger(),
        doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")),
        time=fact(SLOT, ("get_slots", "slot_start"), normalize="datetime-minute", render=to_clock),
    )
    assert line == "You're booked with Dr. Rashmi Indrakanti at 5:00 PM."


def test_model_reconstructed_value_speaks_from_canonical():
    # The model rebuilt the slot with the wrong tz; the spoken time still comes from the
    # canonical tool value, not the model's string.
    line = render_spoken(
        "See you at {time}.",
        ledger=_ledger(),
        time=fact(
            "2026-05-22T17:00:00-05:00",  # wrong offset
            ("get_slots", "slot_start"),
            normalize="datetime-minute",
            render=to_clock,
        ),
    )
    assert line == "See you at 5:00 PM."


def test_canonical_substituted_even_without_render():
    # No renderer -> the canonical tool string is spoken verbatim (not the model's variant).
    line = render_spoken(
        "Doctor is {doctor}.",
        ledger=_ledger(),
        doctor=fact("dr. rashmi indrakanti", ("list_doctors", "doctor_name"), normalize="casefold"),
    )
    assert line == "Doctor is Dr. Rashmi Indrakanti."  # canonical casing, from the tool


def test_ledger_pulled_from_call_context():
    with call_context(tools=_ledger()):
        line = render_spoken(
            "With {doctor}.",
            doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")),
        )
    assert line == "With Dr. Rashmi Indrakanti."


def test_multi_source_fact():
    led = ToolLedger()
    led.record("list_appointments", [{"doctor_name": "Dr. Who"}])
    line = render_spoken(
        "Seeing {doctor}.",
        ledger=led,
        doctor=fact(
            "Dr. Who",
            ("list_doctors", "doctor_name"),
            ("list_appointments", "doctor_name"),
        ),
    )
    assert line == "Seeing Dr. Who."


# ------------------------------- block paths ------------------------------ #


def test_fabricated_fact_refused():
    with pytest.raises(UngroundedSpeech) as excinfo:
        render_spoken(
            "You're booked with {doctor}.",
            ledger=_ledger(),
            doctor=fact("Dr. House", ("list_doctors", "doctor_name")),  # never returned
        )
    assert [b.name for b in excinfo.value.blocked] == ["doctor"]


def test_no_ledger_blocks_everything():
    # Fail-closed: with nothing to ground against, no fact may be spoken.
    with pytest.raises(UngroundedSpeech):
        render_spoken(
            "With {doctor}.",
            ledger=ToolLedger(),
            doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")),
        )


def test_one_bad_fact_blocks_whole_line():
    with pytest.raises(UngroundedSpeech) as excinfo:
        render_spoken(
            "{doctor} at {time}.",
            ledger=_ledger(),
            doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")),  # ok
            time=fact("2026-05-22T13:15:00+05:30", ("get_slots", "slot_start"),
                      normalize="datetime-minute", render=to_clock),  # never offered
        )
    assert [b.name for b in excinfo.value.blocked] == ["time"]


def test_try_render_returns_none_on_block():
    assert try_render_spoken(
        "With {doctor}.",
        ledger=_ledger(),
        doctor=fact("Dr. House", ("list_doctors", "doctor_name")),
    ) is None


def test_try_render_returns_string_on_pass():
    assert try_render_spoken(
        "With {doctor}.",
        ledger=_ledger(),
        doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")),
    ) == "With Dr. Rashmi Indrakanti."


# ------------------------------ usage errors ------------------------------ #


def test_placeholder_without_fact_is_error():
    with pytest.raises(ValueError, match="no grounded fact"):
        render_spoken("Hi {doctor} at {time}.", ledger=_ledger(),
                      doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")))


def test_unused_fact_is_error():
    with pytest.raises(ValueError, match="not referenced"):
        render_spoken("Hello.", ledger=_ledger(),
                      doctor=fact("Dr. Rashmi Indrakanti", ("list_doctors", "doctor_name")))


def test_static_template_text_is_passed_through():
    # No placeholders -> author-written text speaks as-is (no facts needed).
    assert render_spoken("Your appointment is confirmed.", ledger=_ledger()) == (
        "Your appointment is confirmed."
    )


def test_render_exception_blocks_not_leaks():
    def boom(_):
        raise RuntimeError("bad renderer")

    with pytest.raises(UngroundedSpeech):
        render_spoken(
            "At {time}.",
            ledger=_ledger(),
            time=fact(SLOT, ("get_slots", "slot_start"), normalize="datetime-minute", render=boom),
        )
