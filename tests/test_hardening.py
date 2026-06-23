"""Coverage-hardening: internal contracts the feature tests don't exercise.

Covers transcript API surface, value coercion, the supersession guard's
less-common cues, CONFIRMED/INFERABLE internals, result contracts (SteerBack
phrasing, to_dict), from_tool/grounded_outputs spec validation, the sync
@grounded_outputs wrapper, and the testing harness (replay, GroundingCase).

  Observability tests   → tests/test_observe.py
  Normalization tests   → tests/test_normalize.py
  CLI error paths       → tests/test_cli.py
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from saidso import (
    SteerBack,
    ToolLedger,
    Transcript,
    call_context,
    from_tool,
    grounded_outputs,
)
from saidso._matching.matcher import Policy, _is_number, check, to_text
from saidso.result import ArgFinding, GroundingResult, Span
from saidso.testing import GroundingCase, replay


# --------------------------------------------------------------------------- #
# Transcript — full API surface
# --------------------------------------------------------------------------- #


def test_transcript_full_api():
    tr = Transcript.from_pairs([
        ("user", "hello", 1.0),
        ("agent", "hi there"),
        ("user", "my name is Maria"),
    ])
    assert len(tr) == 3
    assert [t.speaker for t in tr] == ["user", "agent", "user"]
    assert len(tr.agent_turns()) == 1
    assert "Maria" in tr.user_text()
    first_id = tr.turns[0].id
    assert len(tr.turns_after(first_id)) == 2
    assert tr.turns[0].to_dict()["speaker"] == "user"
    rows = tr.to_list()
    assert len(rows) == 3 and rows[0]["text"] == "hello"


# --------------------------------------------------------------------------- #
# Value coercion + number sniffing
# --------------------------------------------------------------------------- #


def test_to_text_coercions():
    assert to_text(None) == ""
    assert to_text(True) == "true"
    assert to_text(False) == "false"
    assert to_text(datetime(1990, 1, 1, 5, 30)) == "1990-01-01"
    assert to_text(date(1990, 1, 1)) == "1990-01-01"
    assert to_text(Decimal("5")) == "5"
    assert to_text(5.0) == "5"
    assert to_text(5.5) == "5.5"
    assert to_text("  hi  ") == "hi"


def test_is_number_rejects_bool():
    assert _is_number(5, "5") is True
    assert _is_number(True, "true") is False


# --------------------------------------------------------------------------- #
# Supersession guard — less-common cues
# --------------------------------------------------------------------------- #


def _thr(p):
    from saidso.policy import DEFAULT_THRESHOLDS
    return DEFAULT_THRESHOLDS[p]


def _spoken(value, tr):
    from saidso.context import CallContext
    return check(value, Policy.SPOKEN, tr, CallContext(transcript=tr), _thr(Policy.SPOKEN))


def test_phone_previous_and_used_to_be():
    tr = Transcript()
    tr.add_user("My previous number was 555-1234. Now use 555-9999.")
    assert not _spoken("5551234", tr).grounded
    assert _spoken("5559999", tr).grounded


def test_number_superseded_via_instead():
    tr = Transcript()
    tr.add_user("Put down 4 guests instead of 2.")
    assert _spoken(4, tr).grounded
    assert not _spoken(2, tr).grounded


def test_name_superseded_via_instead():
    tr = Transcript()
    tr.add_user("instead of Johnathan Smith, use Maria Gomez")
    assert not _spoken("Johnathan Smith", tr).grounded
    assert _spoken("Maria Gomez", tr).grounded


# --------------------------------------------------------------------------- #
# CONFIRMED read-back internals + INFERABLE fallback
# --------------------------------------------------------------------------- #


def _confirmed(value, tr):
    from saidso.context import CallContext
    return check(
        value, Policy.CONFIRMED, tr, CallContext(transcript=tr), _thr(Policy.CONFIRMED)
    )


def test_confirmed_readback_phone_number_date():
    # phone read back; caller affirms after a filler turn
    tr = Transcript()
    tr.add_agent("I have your number as 555-123-4567, correct?")
    tr.add_user("um")           # filler — skipped
    tr.add_user("yes exactly")  # affirmation
    assert _confirmed("5551234567", tr).grounded

    # number read back and confirmed
    trn = Transcript()
    trn.add_agent("So that's 3 guests?")
    trn.add_user("correct")
    assert _confirmed(3, trn).grounded

    # date read back and confirmed
    trd = Transcript()
    trd.add_agent("Your date of birth is 1990-01-01, right?")
    trd.add_user("that's right")
    assert _confirmed("1990-01-01", trd).grounded


def test_confirmed_blocks_when_never_read_back():
    tr = Transcript()
    tr.add_user("My name is Maria Gomez.")  # caller said it; agent never read it back
    assert not _confirmed("Maria Gomez", tr).grounded


def test_inferable_falls_back_to_spoken():
    tr = Transcript()
    tr.add_user("The amount is 1200 dollars.")
    from saidso.context import CallContext
    res = check(
        1200, Policy.INFERABLE, tr, CallContext(transcript=tr), _thr(Policy.INFERABLE)
    )
    assert res.grounded


# --------------------------------------------------------------------------- #
# Result contracts — SteerBack phrasing and to_dict
# --------------------------------------------------------------------------- #


def _fail(name):
    return ArgFinding(
        name=name,
        result=GroundingResult(grounded=False, confidence=0.0, policy="spoken", value="x"),
    )


def test_steerback_messages_scale_with_arg_count():
    one = SteerBack("act", failed=[_fail("dob")])
    assert "your date of birth" in one.message
    assert one.to_tool_message() == one.message
    assert bool(one) is False

    two = SteerBack("act", failed=[_fail("dob"), _fail("phone")])
    assert " and " in two.message

    three = SteerBack("act", failed=[_fail("dob"), _fail("phone"), _fail("name")])
    assert ", and " in three.message

    none = SteerBack("act", failed=[])
    assert "an argument was not grounded" in none.message
    assert none.to_dict()["blocked"] is True


def test_result_to_dict_with_span():
    span = Span(turn_id=0, ts=1.0, speaker="user", text="hi")
    gr = GroundingResult(
        grounded=True, confidence=0.9, policy="spoken", value="v", span=span
    )
    d = gr.to_dict()
    assert d["span"]["speaker"] == "user" and d["grounded"] is True


# --------------------------------------------------------------------------- #
# from_tool / grounded_outputs spec validation
# --------------------------------------------------------------------------- #


def test_from_tool_validation_errors():
    with pytest.raises(ValueError):
        from_tool()                             # no sources
    with pytest.raises(ValueError):
        from_tool("only_tool")                  # single-source needs (tool, key)
    with pytest.raises(ValueError):
        from_tool(("t",))                       # pair must have exactly 2 strings
    with pytest.raises(ValueError):
        from_tool("t", "k", normalize="not-a-normalizer")


def test_from_tool_multi_source_label():
    spec = from_tool(("list_doctors", "doctor_id"), ("list_appts", "doctor_id"))
    assert spec.label == "list_doctors.doctor_id|list_appts.doctor_id"


def test_grounded_outputs_spec_validation():
    with pytest.raises(ValueError):
        grounded_outputs()                      # needs at least one spec
    with pytest.raises(TypeError):
        grounded_outputs(slot="not-a-from_tool-spec")


def test_reconcile_normalizer_no_match():
    from saidso import reconcile
    from saidso.provenance import Status

    r = reconcile("xyz", ["abc", "def"], normalize="casefold")
    assert not r.passed and r.status is Status.BLOCK_NO_MATCH


# --------------------------------------------------------------------------- #
# Sync @grounded_outputs wrapper
# --------------------------------------------------------------------------- #


def test_sync_grounded_outputs_rewrites_to_canonical():
    seen = {}

    @grounded_outputs(slot=from_tool("get_slots", "slot", normalize="datetime-minute"))
    def book(context, slot):
        seen["slot"] = slot
        return slot

    ledger = ToolLedger()
    ledger.record("get_slots", [
        {"slot": "2026-05-22T09:30:00+05:30"},
        {"slot": "2026-05-22T17:00:00+05:30"},
    ])
    with call_context(tools=ledger):
        # passed positionally → exercises the bind/rewrite slow path;
        # model passed a wrong tz offset for the same instant
        out = book(None, "2026-05-22T17:00:00-05:00")
    assert seen["slot"] == "2026-05-22T17:00:00+05:30"
    assert out == "2026-05-22T17:00:00+05:30"


def test_sync_grounded_outputs_pass_and_block():
    @grounded_outputs(slot=from_tool("get_slots", "slot"))
    def book(context, slot):
        return {"slot": slot}

    ledger = ToolLedger()
    ledger.record("get_slots", [{"slot": "S1"}, {"slot": "S2"}])
    with call_context(tools=ledger):
        assert book(None, slot="S1") == {"slot": "S1"}
        blocked = book(None, slot="FAKE")
    assert isinstance(blocked, SteerBack)


# --------------------------------------------------------------------------- #
# Testing harness — replay and GroundingCase assertions
# --------------------------------------------------------------------------- #


def test_harness_replay_and_assert_grounded():
    def register(name):
        return f"ok:{name}"

    register.__name__ = "register"
    from saidso import Policy as P
    from saidso import grounded

    guarded = grounded(name=P.SPOKEN)(register)

    case = replay(guarded, [("user", "my name is Maria Gomez")], {"name": "Maria Gomez"})
    case.assert_grounded("ok:Maria Gomez")
    assert case.blocked is False
    assert case.result == "ok:Maria Gomez"

    blocked = GroundingCase(guarded).user("hello").call(name="Imposter Name")
    blocked.assert_blocked("name")
    with pytest.raises(AssertionError):
        blocked.assert_grounded()
