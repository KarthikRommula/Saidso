"""Adversarial / production-hardening tests: the bugs that must never regress."""

from datetime import date

import pytest

from saidso import (
    Policy,
    SteerBack,
    Transcript,
    call_context,
    grounded,
)
from saidso import grounding as G

# --------------------------------------------------------------------------- #
# Numbers: no digit-substring over-matching
# --------------------------------------------------------------------------- #


@grounded(amount=Policy.SPOKEN)
def pay(amount):
    return {"paid": amount}


def test_number_not_grounded_by_superset_digits():
    tr = Transcript()
    tr.add_user("I have called you 20 times about this")
    with call_context(tr):
        out = pay(amount="2")  # caller said 20, not 2
    assert isinstance(out, SteerBack)


def test_float_amount_grounded_from_words():
    tr = Transcript()
    tr.add_user("please send five hundred dollars")
    with call_context(tr):
        assert pay(amount=500.0) == {"paid": 500.0}


def test_int_amount_grounded_from_digits():
    tr = Transcript()
    tr.add_user("transfer 1,250 please")
    with call_context(tr):
        assert pay(amount=1250) == {"paid": 1250}


def test_amount_not_spoken_blocks():
    tr = Transcript()
    tr.add_user("I'd like to make a payment")
    with call_context(tr):
        assert isinstance(pay(amount=500), SteerBack)


# --------------------------------------------------------------------------- #
# Short-string fuzzy over-matching
# --------------------------------------------------------------------------- #


@grounded(name=Policy.SPOKEN)
def reg(name):
    return name


def test_short_name_not_overmatched():
    tr = Transcript()
    tr.add_user("my name is Mariana Lopez")
    with call_context(tr):
        assert isinstance(reg(name="Maria"), SteerBack)  # Maria != Mariana


def test_exact_short_name_still_grounds():
    tr = Transcript()
    tr.add_user("hi it's Sam")
    with call_context(tr):
        assert reg(name="Sam") == "Sam"


# --------------------------------------------------------------------------- #
# Decoration-time validation
# --------------------------------------------------------------------------- #


def test_typo_in_policy_key_raises():
    with pytest.raises(ValueError, match="not parameters"):
        @grounded(dpb=Policy.SPOKEN)
        def _bad(dob):
            return dob


def test_unknown_policy_string_raises():
    with pytest.raises(ValueError, match="unknown policy"):
        @grounded(name="teleport")
        def _bad(name):
            return name


def test_no_policies_raises():
    with pytest.raises(ValueError, match="at least one"):
        @grounded()
        def _bad(name):
            return name


def test_var_kwargs_function_allows_any_guard():
    @grounded(name=Policy.SPOKEN)
    def flexible(**kwargs):
        return kwargs

    tr = Transcript()
    tr.add_user("my name is Dana Wu")
    with call_context(tr):
        assert flexible(name="Dana Wu") == {"name": "Dana Wu"}


# --------------------------------------------------------------------------- #
# Fail-closed on unexpected matcher error
# --------------------------------------------------------------------------- #


def test_fail_closed_when_matcher_raises(monkeypatch):
    ran = []

    @grounded(name=Policy.SPOKEN)
    def book(name):
        ran.append(name)
        return "BOOKED"

    def boom(*a, **k):
        raise RuntimeError("matcher exploded")

    monkeypatch.setattr(G.matcher, "check", boom)
    tr = Transcript()
    tr.add_user("my name is Real Person")
    with call_context(tr):
        out = book(name="Real Person")
    assert isinstance(out, SteerBack)  # blocked, not crashed
    assert ran == []  # body never ran


# --------------------------------------------------------------------------- #
# Type-correct values
# --------------------------------------------------------------------------- #


@grounded(dob=Policy.SPOKEN)
def visit(dob):
    return dob


def test_date_object_argument():
    tr = Transcript()
    tr.add_user("born January first nineteen ninety")
    with call_context(tr):
        assert visit(dob=date(1990, 1, 1)) == date(1990, 1, 1)


# --------------------------------------------------------------------------- #
# Missing context fails closed
# --------------------------------------------------------------------------- #


def test_missing_context_blocks_everything():
    @grounded(name=Policy.SPOKEN)
    def book(name):
        return name

    # No call_context active and no override.
    out = book(name="Anyone")
    assert isinstance(out, SteerBack)


# --------------------------------------------------------------------------- #
# CONFIRMED tolerates filler turns
# --------------------------------------------------------------------------- #


@grounded(name=Policy.CONFIRMED)
def confirm_name(name):
    return name


def test_confirmed_skips_filler_before_yes():
    tr = Transcript()
    tr.add_agent("I have your name as Priya Nair, is that right?")
    tr.add_user("um")
    tr.add_user("uh, yes that's correct")
    with call_context(tr):
        assert confirm_name(name="Priya Nair") == "Priya Nair"
