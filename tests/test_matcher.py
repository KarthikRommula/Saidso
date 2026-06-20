from datetime import date

from saidso import Transcript
from saidso._matching.matcher import check
from saidso.context import CallContext
from saidso.policy import DEFAULT_THRESHOLDS, Policy


def ctx(transcript, **kw):
    return CallContext(transcript=transcript, **kw)


def thr(p):
    return DEFAULT_THRESHOLDS[p]


def test_spoken_name_pass_and_fail():
    tr = Transcript()
    tr.add_user("Hi, my name is Maria Gomez and I'd like to book a visit.")
    c = ctx(tr)

    ok = check("Maria Gomez", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN))
    assert ok.grounded and ok.span is not None

    bad = check("John Doe", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN))
    assert not bad.grounded


def test_spoken_dob_components():
    tr = Transcript()
    tr.add_user("My date of birth is January first, nineteen ninety.")
    c = ctx(tr)
    ok = check("1990-01-01", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN))
    assert ok.grounded
    assert ok.normalized == "1990-01-01"


def test_spoken_dob_missing_is_blocked():
    tr = Transcript()
    tr.add_user("Hi, I'd like to make an appointment please.")
    c = ctx(tr)
    bad = check("1990-01-01", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN))
    assert not bad.grounded


def test_confirmed_pass_and_reject():
    tr = Transcript()
    tr.add_user("It's Maria Gomez.")
    tr.add_agent("Great, I have your name as Maria Gomez, is that correct?")
    tr.add_user("Yes, that's right.")
    c = ctx(tr)
    ok = check("Maria Gomez", Policy.CONFIRMED, tr, c, thr(Policy.CONFIRMED))
    assert ok.grounded

    tr2 = Transcript()
    tr2.add_agent("I have your name as Maria Gomez, correct?")
    tr2.add_user("No, that's wrong.")
    bad = check("Maria Gomez", Policy.CONFIRMED, tr2, ctx(tr2), thr(Policy.CONFIRMED))
    assert not bad.grounded


def test_caller_id_uses_metadata_not_speech():
    tr = Transcript()
    tr.add_user("I never said my number out loud.")
    c = ctx(tr, metadata={"caller_id": "+1 (555) 123-4567"})
    ok = check("5551234567", Policy.CALLER_ID, tr, c, thr(Policy.CALLER_ID))
    assert ok.grounded and ok.confidence == 1.0

    c2 = ctx(tr, metadata={})
    bad = check("5551234567", Policy.CALLER_ID, tr, c2, thr(Policy.CALLER_ID))
    assert not bad.grounded


def test_superseded_phone_is_not_grounded():
    tr = Transcript()
    tr.add_user("My old number was 555-1234 but use 555-9999 from now on.")
    c = ctx(tr)

    dead = check("5551234", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN))
    assert not dead.grounded  # the retracted/old number must not commit

    live = check("5559999", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN))
    assert live.grounded  # the replacement is fine


def test_negated_name_is_not_grounded():
    tr = Transcript()
    tr.add_user("My name is not John Doe, it's Maria Gomez.")
    c = ctx(tr)
    assert not check("John Doe", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded
    assert check("Maria Gomez", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded


def test_superseded_number_then_corrected():
    tr = Transcript()
    tr.add_user("I have 2 kids, I mean 3 kids.")
    c = ctx(tr)
    assert not check(2, Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded
    assert check(3, Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded


def test_corrected_date_does_not_ground_the_old_one():
    tr = Transcript()
    tr.add_user("Book me for January 5th 2026, no wait, January 6th 2026.")
    c = ctx(tr)
    assert not check("2026-01-05", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded
    assert check("2026-01-06", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded


def test_plain_mention_still_grounds_without_correction():
    # Guard must not over-block ordinary, uncorrected speech.
    tr = Transcript()
    tr.add_user("My number is 555-9999 and my name is Maria Gomez.")
    c = ctx(tr)
    assert check("5559999", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded
    assert check("Maria Gomez", Policy.SPOKEN, tr, c, thr(Policy.SPOKEN)).grounded


def test_inferable_relative_date():
    tr = Transcript()
    tr.add_user("Can I come in tomorrow?")
    c = ctx(tr, now=date(2026, 6, 19))
    ok = check("2026-06-20", Policy.INFERABLE, tr, c, thr(Policy.INFERABLE))
    assert ok.grounded
