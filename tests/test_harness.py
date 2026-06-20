"""Tests for the saidso.testing replay harness."""

from saidso import Policy, grounded
from saidso.testing import GroundingCase, replay


@grounded(name=Policy.SPOKEN, dob=Policy.SPOKEN)
def register_patient(name, dob):
    return {"committed": True, "name": name, "dob": dob}


def test_case_blocks_invented_values():
    (
        GroundingCase(register_patient)
        .user("Hi, I'd like an appointment")
        .call(name="John Doe", dob="1990-01-01")
        .assert_blocked("name", "dob")
    )


def test_case_grounds_real_values_and_records_attestation():
    case = (
        GroundingCase(register_patient)
        .user("It's Maria Gomez, born January first nineteen ninety")
        .call(name="Maria Gomez", dob="1990-01-01")
        .assert_grounded()
    )
    assert case.result["committed"] is True
    assert len(case.attestations) == 1


def test_replay_helper():
    case = replay(
        register_patient,
        [("user", "this is Sam Rivera, born March third two thousand")],
        {"name": "Sam Rivera", "dob": "2000-03-03"},
    )
    assert not case.blocked
