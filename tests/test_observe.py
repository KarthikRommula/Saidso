"""Observability: structured events, pretty formatting, recorder, summary."""

from __future__ import annotations

import logging

from saidso import (
    AttestationLog,
    EventRecorder,
    Policy,
    Transcript,
    call_context,
    enable_pretty_logging,
    grounded,
    summary,
)
from saidso.observe import PrettyFormatter, _supports_color
from saidso.result import ArgFinding, GroundingResult


# --------------------------------------------------------------------------- #
# PrettyFormatter
# --------------------------------------------------------------------------- #


def _record(event, action, args, *, color=False):
    rec = logging.LogRecord("saidso", logging.INFO, __file__, 1, "msg", (), None)
    rec.saidso_event = event
    rec.saidso_action = action
    rec.saidso_args = args
    return PrettyFormatter(color=color).format(rec)


def test_formatter_plain_pass():
    line = _record("pass", "register_patient", ["name", "dob"])
    assert "grounded" in line and "register_patient" in line and "name, dob" in line
    assert "\033[" not in line


def test_formatter_color_adds_ansi():
    line = _record("block", "book", ["slot_start"], color=True)
    assert "\033[" in line
    assert "blocked" in line and "book" in line


def test_formatter_non_saidso_record():
    rec = logging.LogRecord("saidso", logging.INFO, __file__, 1, "plain message", (), None)
    out = PrettyFormatter(color=False).format(rec)
    assert "plain message" in out


def test_formatter_unknown_event():
    rec = logging.LogRecord("saidso", logging.INFO, __file__, 1, "m", (), None)
    rec.saidso_event = "error"
    rec.saidso_action = "act"
    rec.saidso_args = ["x"]
    assert "error" in PrettyFormatter(color=False).format(rec)


# --------------------------------------------------------------------------- #
# _supports_color
# --------------------------------------------------------------------------- #


def test_supports_color_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert _supports_color(None) is False


def test_supports_color_force_color_env(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert _supports_color(None) is True


# --------------------------------------------------------------------------- #
# EventRecorder
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #


def test_summary_counts_from_recorder():
    rec = EventRecorder()
    rec.events = [
        {"event": "pass", "action": "book", "args": ["slot_start"], "ts": 0},
        {"event": "block", "action": "register", "args": ["dob"], "ts": 0},
    ]
    out = summary(recorder=rec)
    assert "1 grounded, 1 blocked" in out
    assert "✓ book" in out and "✗ register" in out


def test_summary_audit_only():
    log = AttestationLog()
    finding = ArgFinding(
        name="dob",
        result=GroundingResult(grounded=True, confidence=1.0, policy="spoken", value="x"),
    )
    log.build("register", [finding], call_id="c1")
    out = summary(audit=log)
    assert "1 grounded, 0 blocked" in out and "register" in out


def test_summary_empty():
    assert "no decisions recorded" in summary()


# --------------------------------------------------------------------------- #
# enable_pretty_logging
# --------------------------------------------------------------------------- #


def test_pretty_logging_emits_colored_line():
    import io

    stream = io.StringIO()
    handler = enable_pretty_logging(color=True, stream=stream)
    try:
        logging.getLogger("saidso").info(
            "grounded act: ['name']",
            extra={"saidso_event": "pass", "saidso_action": "act", "saidso_args": ["name"]},
        )
        out = stream.getvalue()
        assert "\033[" in out and "act" in out
    finally:
        logging.getLogger("saidso").removeHandler(handler)


def test_enable_pretty_logging_is_idempotent():
    enable_pretty_logging(color=False)
    h2 = enable_pretty_logging(color=False)
    saidso_handlers = [
        h for h in logging.getLogger("saidso").handlers
        if getattr(h, "_saidso_pretty", False)
    ]
    assert len(saidso_handlers) == 1  # second call replaced the first
    logging.getLogger("saidso").removeHandler(h2)
