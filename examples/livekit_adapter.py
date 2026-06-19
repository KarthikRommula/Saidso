"""Sketch: feeding a LiveKit Agents session into saidso.

LiveKit emits transcription events for both the user and the agent. The adapter
job is small: keep a :class:`Transcript` in sync and open a ``call_context`` so
your ``@grounded`` tools read from it automatically.

This is a roadmap stub showing the integration shape — it is not a runnable
LiveKit app. See ROADMAP.md for the planned first-class adapter.
"""

from __future__ import annotations

from saidso import AttestationLog, Policy, Transcript, call_context, grounded, set_context
from saidso.context import CallContext


@grounded(name=Policy.SPOKEN, phone=Policy.CALLER_ID)
def update_contact(name, phone):
    return {"updated": True, "name": name, "phone": phone}


def attach_to_session(session, caller_id: str):
    """Pseudo-wiring against a LiveKit ``AgentSession``-like object."""
    transcript = Transcript()
    ledger = AttestationLog(path="attestations.jsonl")

    # Make every @grounded tool in this session read from our transcript.
    set_context(CallContext(transcript=transcript, metadata={"caller_id": caller_id}, ledger=ledger))

    @session.on("user_speech_committed")
    def _on_user(ev):  # ev.alternatives[0].text in real LiveKit
        transcript.add_user(ev.text)

    @session.on("agent_speech_committed")
    def _on_agent(ev):
        transcript.add_agent(ev.text)

    return transcript, ledger
