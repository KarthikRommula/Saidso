import asyncio

import pytest

from saidso import (
    AttestationLog,
    GroundingBlocked,
    GroundingConfig,
    Policy,
    SteerBack,
    Transcript,
    call_context,
    grounded,
)


def make_tool():
    calls = []

    @grounded(name=Policy.SPOKEN, dob=Policy.SPOKEN)
    def register_patient(name, dob):
        calls.append((name, dob))
        return {"ok": True, "name": name, "dob": dob}

    return register_patient, calls


def test_john_doe_is_blocked_body_never_runs():
    tool, calls = make_tool()
    tr = Transcript()
    tr.add_user("Hi, I'd like to book an appointment.")
    with call_context(tr):
        out = tool(name="John Doe", dob="1990-01-01")
    assert isinstance(out, SteerBack)
    assert out.blocked
    assert calls == []  # the body never executed
    failed_args = {f.name for f in out.failed}
    assert failed_args == {"name", "dob"}
    assert "date of birth" in out.message


def test_grounded_call_runs_and_attests():
    tool, calls = make_tool()
    tr = Transcript()
    tr.add_user("This is Maria Gomez, born January first nineteen ninety.")
    log = AttestationLog()
    with call_context(tr, ledger=log, call_id="call-1"):
        out = tool(name="Maria Gomez", dob="1990-01-01")
    assert out == {"ok": True, "name": "Maria Gomez", "dob": "1990-01-01"}
    assert calls == [("Maria Gomez", "1990-01-01")]
    assert len(log) == 1
    rec = log.records[0].to_dict()
    assert rec["action"] == "register_patient"
    assert rec["call_id"] == "call-1"
    args = {a["arg"]: a for a in rec["args"]}
    assert args["name"]["span"] is not None  # provenance recorded


def test_partial_grounding_blocks_only_naming_missing():
    tool, _calls = make_tool()
    tr = Transcript()
    tr.add_user("My name is Maria Gomez.")  # name yes, dob never said
    with call_context(tr):
        out = tool(name="Maria Gomez", dob="1990-01-01")
    assert isinstance(out, SteerBack)
    assert {f.name for f in out.failed} == {"dob"}
    assert {f.name for f in out.grounded} == {"name"}


def test_raise_on_block_mode():
    @grounded(GroundingConfig(raise_on_block=True), name=Policy.SPOKEN)
    def book(name):
        return name

    tr = Transcript()
    tr.add_user("nothing relevant here")
    with call_context(tr), pytest.raises(GroundingBlocked):
        book(name="Ghost Caller")


def test_async_tool():
    @grounded(name=Policy.SPOKEN)
    async def book(name):
        return f"booked {name}"

    tr = Transcript()
    tr.add_user("my name is Sam Rivera")

    async def run():
        with call_context(tr):
            return await book(name="Sam Rivera")

    assert asyncio.run(run()) == "booked Sam Rivera"


def test_explicit_transcript_override_is_stripped():
    tool, calls = make_tool()
    tr = Transcript()
    tr.add_user("This is Maria Gomez, born January first nineteen ninety.")
    # no call_context active; pass transcript explicitly
    out = tool(name="Maria Gomez", dob="1990-01-01", _transcript=tr)
    assert out["ok"] is True
    assert calls == [("Maria Gomez", "1990-01-01")]
