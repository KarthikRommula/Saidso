"""Wiring saidso into a raw OpenAI tool-use loop.

The key idea: when the firewall returns a SteerBack, you hand its message back
to the model as the tool result. The model then re-asks the caller and tries
again — self-correction inside the same conversation.

This file is illustrative; it runs the firewall logic for real but stubs the
OpenAI client so it works with no API key. Replace ``FakeClient`` with a real
``openai.OpenAI()`` to use it for real.
"""

from __future__ import annotations

import json

from saidso import AttestationLog, Policy, SteerBack, Transcript, call_context, grounded

log = AttestationLog()
BOOKINGS = []


@grounded(name=Policy.SPOKEN, party_size=Policy.SPOKEN)
def book_table(name, party_size):
    BOOKINGS.append({"name": name, "party_size": party_size})
    return {"confirmed": True, "name": name, "party_size": party_size}


# The tool the model sees. Note: descriptions never name a bad example value
# (anti-priming) — they describe the *rule*, not a placeholder to copy.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_table",
            "description": (
                "Book a restaurant table. Only call this once the caller has "
                "stated their name and party size. Never invent values."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The caller's name, as they said it."},
                    "party_size": {"type": "integer", "description": "Number of people, as stated."},
                },
                "required": ["name", "party_size"],
            },
        },
    }
]


def dispatch_tool_call(call, transcript):
    """Route a model tool call through the firewall."""
    args = json.loads(call["arguments"])
    with call_context(transcript, ledger=log, call_id="demo"):
        result = book_table(**args)
    if isinstance(result, SteerBack):
        # Feed the steer-back back to the model as the tool result.
        return result.to_tool_message()
    return json.dumps(result)


class FakeClient:
    """Stand-in that first hallucinates, then (after steer-back) does it right."""

    def __init__(self):
        self._step = 0

    def next_tool_call(self, transcript):
        self._step += 1
        if self._step == 1:
            return {"name": "book_table", "arguments": json.dumps({"name": "John Doe", "party_size": 4})}
        return {"name": "book_table", "arguments": json.dumps({"name": "Maria Gomez", "party_size": 2})}


def main():
    client = FakeClient()
    tr = Transcript()
    tr.add_user("Hi, can I get a table?")

    # Turn 1: model hallucinates -> firewall steers back.
    call = client.next_tool_call(tr)
    tool_result = dispatch_tool_call(call, tr)
    print("turn 1 tool result ->", tool_result)
    assert "John Doe" not in str(BOOKINGS)

    # Model re-asks; caller answers.
    tr.add_agent("Sure — what's the name and how many people?")
    tr.add_user("Maria Gomez, table for two.")

    # Turn 2: grounded -> committed + attested.
    call = client.next_tool_call(tr)
    tool_result = dispatch_tool_call(call, tr)
    print("turn 2 tool result ->", tool_result)
    print("bookings:", BOOKINGS)
    print("attestations:", json.dumps(log.export(), indent=2))


if __name__ == "__main__":
    main()
