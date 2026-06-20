# integrate — wire saidso into any agent stack

saidso imports no model SDK. It operates on three things every stack has: the
conversation text, your tool functions, and recorded tool outputs. Integrating is a
small adapter with three hooks.

## The three hooks

1. WRITES — keep a Transcript in sync with the conversation, and open a
   call_context around tool execution:

     from saidso import Transcript, call_context, AttestationLog, ToolLedger

     tr = Transcript()
     # on each turn: tr.add_user(text) / tr.add_agent(text)
     with call_context(tr, ledger=AttestationLog(), tools=ToolLedger(),
                       metadata={"caller_id": caller_phone}):
         result = run_the_tool(...)

2. PROVENANCE — after each read tool returns, record it so write tools can ground
   ids/timestamps against real output:

     userdata.tool_ledger.record("get_slots", rows)

3. READS — hand render_spoken()'s verified string to your TTS. On a native-audio
   model, also suppress the model's own turn so it doesn't double-speak.

## Per platform

- Raw OpenAI / Anthropic tool-use: return the SteerBack message as the tool result
  so the model self-corrects; pass arguments through the decorated tool.
- Cascaded STT -> LLM -> TTS: you already control the TTS — feed it render_spoken's
  string directly. Easiest case.
- Native-audio realtime (Gemini Live, OpenAI Realtime): add a side TTS and speak
  the verified string via the platform's say() while stopping the model turn.
- Text agents: render_spoken's string IS the output.

## What's universal vs platform-specific

- Writes: 100% on every stack — the tool-call boundary is identical everywhere.
- Reads: the verification (render_spoken) is universal; DELIVERING the verified
  text as audio is the only platform-specific part (trivial for pipelines/text;
  needs a side-TTS lane for native-audio models).

See bundled adapters in the sdist: examples/openai_tooluse.py,
examples/livekit_adapter.py.
