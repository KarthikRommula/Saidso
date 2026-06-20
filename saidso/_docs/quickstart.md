# quickstart

## Install

  pip install saidso          # zero required dependencies
  pip install saidso[fast]    # optional rapidfuzz for faster matching

## Scaffold a runnable example

  saidso quickstart           # writes quickstart.py + GETTING_STARTED.md
  python saidso-quickstart/quickstart.py

## Minimal example

  from saidso import grounded, Policy, Transcript, call_context

  @grounded(name=Policy.SPOKEN, dob=Policy.SPOKEN)
  def register_patient(name, dob):
      ...  # your real DB write — only runs if BOTH are grounded

  tr = Transcript()
  tr.add_user("It's Maria Gomez, born January first nineteen ninety.")

  with call_context(tr):
      out = register_patient(name="Maria Gomez", dob="1990-01-01")  # commits

  # A blocked call returns a SteerBack instead of running the body:
  if getattr(out, "blocked", False):
      say_to_caller(out.message)   # the agent re-asks; nothing was committed

## What happened

- `@grounded` checked each argument against the transcript before the body ran.
- "Maria Gomez" + the spoken DOB are present -> the write executed.
- A fabricated value would have been blocked, and `out.message` tells the agent
  exactly what to re-ask.

Next:  saidso docs writes   ·   saidso docs reads
