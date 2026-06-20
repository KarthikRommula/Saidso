"""Observability: structured events, pretty formatting, recorder, summary."""

from __future__ import annotations

import logging

from saidso import (
    EventRecorder,
    Policy,
    Transcript,
    call_context,
    enable_pretty_logging,
    grounded,
    summary,
)
from saidso.observe import PrettyFormatter


def _record(event, action, args, *, color=False):
    rec = logging.LogRecord("saidso", logging.INFO, __file__, 1, "msg", (), None)
    rec.saidso_event = event
    rec.saidso_action = action
    rec.saidso_args = args
    return PrettyFormatter(color=color).format(rec)


def test_formatter_plain_pass():
    line = _record("pass", "register_patient", ["name", "dob"])
    assert "grounded" in line and "register_patient" in line and "name, dob" in line
    assert "\033[" not in line  # no color codes when color=False


def test_formatter_color_adds_ansi():
    line = _record("block", "book", ["slot_start"], color=True)
    assert "\033[" in line  # ANSI present
    assert "blocked" in line and "book" in line


def test_recorder_captures_pass_and_block():
    @grounded(name=Policy.SPOKEN)
    def act(name):
        return True

    rec = EventRecorder()
    logging.getLogger("saidso").addHandler(rec)
    logging.getLogger("saidso").setLevel(logging.INFO)
    try:
        tr = Transcript()
        tr.add_user("My name is Maria.")
        with call_context(tr):
            act(name="Maria")   # pass
            act(name="Robert")  # block
    finally:
        logging.getLogger("saidso").removeHandler(rec)

    assert len(rec.passed) == 1
    assert len(rec.blocked) == 1
    assert rec.passed[0]["action"] == "act"


def test_summary_counts_from_recorder():
    rec = EventRecorder()
    rec.events = [
        {"event": "pass", "action": "book", "args": ["slot_start"], "ts": 0},
        {"event": "block", "action": "register", "args": ["dob"], "ts": 0},
    ]
    out = summary(recorder=rec)
    assert "1 grounded, 1 blocked" in out
    assert "✓ book" in out and "✗ register" in out


def test_enable_pretty_logging_is_idempotent():
    enable_pretty_logging(color=False)
    h2 = enable_pretty_logging(color=False)
    saidso_handlers = [
        h for h in logging.getLogger("saidso").handlers
        if getattr(h, "_saidso_pretty", False)
    ]
    assert len(saidso_handlers) == 1  # second call replaced the first
    logging.getLogger("saidso").removeHandler(h2)
