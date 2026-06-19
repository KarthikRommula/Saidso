# saidso — roadmap

The MVP is deliberately small and deterministic. These are the pieces that turn
it from a useful decorator into a category-defining tool.

## 1. Verifier-model escalation
When deterministic matching lands in the ambiguous band (near the threshold),
escalate that single argument to a tiny, fast model: "Did the caller say X?
Quote the words." Keep it off the hot path; cache per-turn. Pluggable backend.

## 2. Anti-priming prompt compiler
Generate tool descriptions and guard prompts that enforce fidelity **without
ever naming a bad example value** (example values teach the model to emit them).
Input: the function signature + policies. Output: a description block + system
guidance. This is a hard-won, little-known lesson baked into a generator.

## 3. Hallucination regression harness
A pytest-style harness: replay real or synthetic transcripts against guarded
tools and assert **zero ungrounded commits** slipped through. Turns "we hope it
doesn't fabricate" into a CI gate. Ships with a corpus format and fixtures.

## 4. First-class framework adapters
- **LiveKit** (priority — home turf): transcription events → `Transcript`,
  auto `call_context` per session.
- **Pipecat**, **Vapi**, **LangGraph** tool nodes.
Keep each adapter thin; the core stays framework-neutral.

## 5. Matcher precision/recall eval set
A brutal labeled set of (transcript, value, expected verdict) — accents, ASR
noise, spelled-out emails, partial confirmations. Publish precision/recall.
**This is what determines whether anyone keeps the firewall on.** Build it
before the launch tweet.

## 6. Richer policies
- `Policy.SPOKEN(type=...)` explicit type hints (date/phone/email/name).
- `Policy.ONE_OF([...])` for enum-ish slots.
- Composable policies (`SPOKEN | CONFIRMED`).
- `email` normalization ("m as in mango, a, r, i, a, at gmail dot com").

## 7. Provenance ledger as a product surface
Exportable, signed attestation bundles ("authorized by these words at 00:42")
for healthcare/finance/legal audit. The likely paid layer on top of the OSS
core.

## 8. Observability
Per-call metrics: block rate, false-block feedback loop, latency budget, policy
hit rates. A dashboard is downstream of this.
