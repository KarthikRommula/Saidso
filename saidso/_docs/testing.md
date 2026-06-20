# testing — turn the guarantee into a CI gate

Assert that invented values are blocked and real ones commit. This converts "we
hope it doesn't fabricate" into a test that fails the build if it ever does.

  from saidso.testing import GroundingCase

  def test_invented_dob_is_blocked():
      (GroundingCase(register_patient)
          .user("Hi, I'd like an appointment")
          .call(name="John Doe", dob="1990-01-01")
          .assert_blocked("name", "dob"))

  def test_real_values_commit():
      (GroundingCase(register_patient)
          .user("It's Maria Gomez, born January first nineteen ninety")
          .call(name="Maria Gomez", dob="1990-01-01")
          .assert_grounded())

## How it reads

- GroundingCase(tool) — the guarded function under test.
- .user(text) — add a caller turn to the transcript (chain several).
- .agent(text) — add an agent turn (needed for CONFIRMED read-backs).
- .call(**kwargs) — invoke the tool with these arguments.
- .assert_blocked(*args) — expect a block; optionally name the args that failed.
- .assert_grounded() — expect the call to pass and the body to run.

Put these in your normal pytest suite. They run in-process, deterministically, with
no model and no network — so they're fast and stable in CI.

Next:  saidso docs writes   ·   saidso docs observability
