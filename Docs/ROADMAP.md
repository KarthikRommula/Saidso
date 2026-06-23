# Roadmap

The core library is deliberately small and deterministic. These are the pieces
that turn it from a useful decorator into a category-defining tool.

---

## 1. Verifier-model escalation

When deterministic matching lands in the ambiguous band (near the confidence
threshold), escalate that single argument to a small, fast model: "Did the
caller say X? Quote the words." Keep it off the hot path; cache the verdict
per transcript turn. The interface is pluggable — any model that returns a
structured yes/no with a quoted span qualifies.

## 2. Anti-priming prompt compiler

Generate tool descriptions and system prompts that enforce fidelity **without
ever naming a placeholder example value** (example values teach the model to
emit them). Input: a function signature plus its `@grounded` policies. Output:
a description block and system guidance. This is a hard-won, little-known
lesson from production voice deployments, baked into a generator.

## 3. Matcher precision/recall eval set

A labeled dataset of `(transcript, argument_value, expected_verdict)` triples
covering accents, ASR noise, spelled-out emails, partial confirmations, and
correction flows. Publish precision/recall by policy and normalization type.
**This is what determines whether a team keeps the firewall enabled.** Build
and publish this before any broad launch.

## 4. First-class framework adapters

- **LiveKit Agents** (priority): transcription events → `Transcript`, automatic
  `call_context` per session.
- **Pipecat**, **Vapi**, **LangGraph** tool nodes.

Each adapter must be thin — a few dozen lines that bridge the framework's
event model to saidso's `Transcript` and `call_context`. The core stays
framework-neutral.

## 5. Richer policies

- `Policy.SPOKEN(type="date" | "phone" | "email" | "name")` — explicit type
  hints that select the right normalizer automatically.
- `Policy.ONE_OF([...])` — enum-style slots (e.g. a department name chosen
  from a known list).
- Composable policies: `SPOKEN | CONFIRMED` for high-stakes arguments.
- `normalize="email"` to handle spelled-out addresses:
  "m as in mango, a, r, i, a, at gmail dot com" → "maria@gmail.com".

## 6. Exportable, signed attestation bundles

Per-call attestation packages — a signed, self-contained record of "this action
was authorized by these caller words at this timestamp" — suitable for
healthcare, finance, and legal audit. The natural paid layer on top of the OSS
core.

## 7. Per-call observability metrics

Block rate, false-block feedback loop, latency budget, and policy hit rates
exposed as structured telemetry (OpenTelemetry spans or a simple JSON summary).
A dashboard is downstream of this; the metrics schema comes first.
