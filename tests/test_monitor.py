"""Best-effort speech-grounding monitor tests (saidso.speech.monitor, PARTIAL feature)."""

from __future__ import annotations

from saidso import check_spoken_names, find_name_mentions, find_ungrounded_names

ALLOWED = ["Dr. John Smith", "Dr. Aisha Patel"]


def test_extracts_titled_names():
    got = find_name_mentions("We have Dr. Smith and Doctor Patel available today.")
    assert got == ["Smith", "Patel"]


def test_all_real_names_grounded():
    assert find_ungrounded_names("You can see Dr. Smith or Dr. Patel.", ALLOWED) == []


def test_hallucinated_name_flagged():
    ung = find_ungrounded_names("We have Dr. Smith and Dr. Jones.", ALLOWED)
    assert [m.text for m in ung] == ["Jones"]


def test_full_name_grounded():
    assert find_ungrounded_names("Dr. John Smith can see you Tuesday.", ALLOWED) == []


def test_hallucinated_surname_with_real_first_name_flagged():
    # 'John' is real but 'Jones' is not — judged on the surname
    ung = find_ungrounded_names("How about Dr. John Jones?", ALLOWED)
    assert [m.text for m in ung] == ["John Jones"]


def test_no_titled_names_is_empty():
    assert find_ungrounded_names("Let me check the schedule for you.", ALLOWED) == []


def test_check_returns_grounded_flag_and_match():
    res = check_spoken_names("See Dr. Patel or Dr. Nguyen.", ALLOWED)
    by_text = {m.text: m for m in res}
    assert by_text["Patel"].grounded is True
    assert by_text["Nguyen"].grounded is False
