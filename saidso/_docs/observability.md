# observability — see and audit every decision

Two layers: a live log stream (pass/block) and an audit trail (passes, with proof).

## Live stream

Every decision emits one structured event on the `saidso` logger
(saidso_event = pass|block, saidso_action, saidso_args). Turn on the pretty console:

  from saidso import enable_pretty_logging, EventRecorder, summary

  enable_pretty_logging()              # colored ✓/✗ (auto-off when not a TTY)
  rec = EventRecorder().attach()       # remember events for a summary
  ...
  print(summary(audit, rec))

Output:

  13:38:15 ✓ grounded register_patient  name, dob
  13:38:15 ✗ blocked  book_appointment  slot_start
  ┌─ saidso — 1 grounded, 1 blocked
    ✓ register_patient       name, dob
    ✗ book_appointment       slot_start
  └──────────────────────────────

For production, skip pretty logging and attach your own handler (the events are
plain fields, JSON-friendly), or set the `saidso` logger level as usual:

  import logging
  logging.getLogger("saidso").setLevel(logging.INFO)

## Audit trail (the receipts)

Every PASSING action records an Attestation: which value came from which words,
when, with what confidence.

  from saidso import AttestationLog, call_context

  audit = AttestationLog(path="audit.jsonl")   # omit path to keep in memory only
  with call_context(transcript, ledger=audit):
      ...

  len(audit)            # how many actions passed
  audit.records         # list of Attestation objects
  audit.export()        # list of dicts (JSON-friendly)

Blocks are NOT in the audit log (nothing happened) — they appear in the logger and
as the SteerBack you receive.

Next:  saidso docs testing
