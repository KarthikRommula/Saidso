"""Wiring saidso into an OpenAI-style tool-use loop.

The key pattern: when the firewall returns a SteerBack, pass its message back
to the model as the tool result. The model then re-asks the caller and retries
with grounded data — self-correction inside the same conversation, with no
changes to the model call structure.

This file runs the firewall logic for real but stubs the OpenAI client so it
works without an API key. Replace FakeClient.next_tool_call() with a real
openai.OpenAI().chat.completions.create(...) call.

Run:
    pip install saidso
    python examples/openai_tooluse.py
"""

from __future__ import annotations

import json

from saidso import AttestationLog, Policy, SteerBack, Transcript, call_context, grounded

log = AttestationLog()
BOOKINGS: list[dict] = []


@grounded(name=Policy.SPOKEN, party_size=Policy.SPOKEN)
def book_table(name: str, party_size: int) -> dict:
    BOOKINGS.append({"name": name, "party_size": party_size})
    return {"confirmed": True, "name": name, "party_size": party_size}


# Tool schema sent to the model.
# Descriptions state the rule the caller must satisfy.
# Never include a placeholder example value — that teaches the model to emit it.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_table",
            "description": (
                "Book a restaurant table. Call only after the caller has stated "
                "their name and party size. Do not invent values not in the transcript."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The caller's name, exactly as stated.",
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of guests, exactly as stated.",
                    },
                },
                "required": ["name", "party_size"],
            },
        },
    }
]


def dispatch_tool_call(call: dict, transcript: Transcript) -> str:
    """Route one model tool call through the firewall and return the tool result."""
    args = json.loads(call["arguments"])
    with call_context(transcript, ledger=log, call_id="demo"):
        result = book_table(**args)
    if isinstance(result, SteerBack):
        # Return the steer-back message as the tool result so the model
        # re-asks the caller for the missing or ungrounded data.
        return result.to_tool_message()
    return json.dumps(result)


class FakeClient:
    """Simulates a model that hallucinates on turn 1, then grounds on turn 2."""

    def __init__(self) -> None:
        self._step = 0

    def next_tool_call(self, _transcript: Transcript) -> dict:
        self._step += 1
        if self._step == 1:
            # The caller gave no name. The model invents one.
            return {
                "name": "book_table",
                "arguments": json.dumps({"name": "John Doe", "party_size": 4}),
            }
        # After the steer-back the model uses the name the caller actually gave.
        return {
            "name": "book_table",
            "arguments": json.dumps({"name": "Maria Gomez", "party_size": 2}),
        }


def main() -> None:
    client = FakeClient()
    tr = Transcript()
    tr.add_user("Hi, can I get a table?")

    # Turn 1: model hallucinates → firewall blocks, returns steer-back message.
    call = client.next_tool_call(tr)
    result = dispatch_tool_call(call, tr)
    print("turn 1 →", result)
    assert "John Doe" not in str(BOOKINGS), "fabricated name must not be committed"

    # Model re-asks; caller provides real data.
    tr.add_agent("Of course — what name and how many guests?")
    tr.add_user("Maria Gomez, table for two please.")

    # Turn 2: both args trace to the caller's words → committed and attested.
    call = client.next_tool_call(tr)
    result = dispatch_tool_call(call, tr)
    print("turn 2 →", result)
    print("bookings:", BOOKINGS)
    print("attestations:", json.dumps(log.export(), indent=2))


if __name__ == "__main__":
    main()
