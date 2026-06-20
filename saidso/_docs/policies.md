# policies — the rule for an argument (@grounded)

A Policy says HOW an argument must be proven.

  SPOKEN      the value appears in the caller's speech (digits/dates/names
              normalized and fuzzy-matched)
  CONFIRMED   the agent read the value back AND the caller affirmed it
  CALLER_ID   the value matches trusted call metadata, not what was spoken
  INFERABLE   the value is derivable from context ("tomorrow" + clock) or spoken

## Examples

  from saidso import grounded, Policy

  @grounded(
      name=Policy.SPOKEN,          # caller said it
      phone=Policy.CALLER_ID,      # from the phone line, not the model
      email=Policy.CONFIRMED,      # agent read it back, caller said "yes"
      visit_date=Policy.INFERABLE, # "next Tuesday" -> resolved from the clock
  )
  def register(name, phone, email, visit_date): ...

## Choosing one

- Use SPOKEN for plain facts the caller states (name, DOB, gender).
- Use CONFIRMED for high-stakes or error-prone values (a spelled-out email, an
  amount) — it requires an explicit read-back + "yes".
- Use CALLER_ID for the caller's own phone number (carrier metadata is more
  trustworthy than transcription). Provide it via
  call_context(..., metadata={"caller_id": "+1..."}).
- Use INFERABLE for relative dates/times.

## Tuning

Thresholds are per-policy and adjustable:

  from saidso import GroundingConfig, Policy
  cfg = GroundingConfig(thresholds={Policy.SPOKEN: 0.9})
  @grounded(cfg, name=Policy.SPOKEN)
  def f(name): ...

Note: for grounding against tool OUTPUT (ids, slots) you don't use a Policy — you
use @grounded_outputs + from_tool. See `saidso docs writes`.
