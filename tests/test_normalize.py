from datetime import date

from saidso._matching import normalize as N


def test_words_to_int():
    assert N.words_to_int("forty two") == 42
    assert N.words_to_int("two thousand five") == 2005
    assert N.words_to_int("one hundred twenty three") == 123
    assert N.words_to_int("zero") == 0
    assert N.words_to_int("banana") is None


def test_find_years():
    assert 1990 in N.find_years("nineteen ninety")
    assert 1984 in N.find_years("nineteen eighty four")
    assert 2005 in N.find_years("two thousand five")
    assert 2024 in N.find_years("twenty twenty four")
    assert 1990 in N.find_years("born in 1990")


def test_normalize_date_iso_and_textual():
    assert N.normalize_date("1990-01-01") == "1990-01-01"
    assert N.normalize_date("January 1, 1990") == "1990-01-01"
    assert N.normalize_date("1 January 1990") == "1990-01-01"
    assert N.normalize_date("January first, nineteen ninety") == "1990-01-01"
    assert N.normalize_date("3/14/1990") == "1990-03-14"


def test_normalize_date_relative():
    now = date(2026, 6, 19)
    assert N.normalize_date("tomorrow", now) == "2026-06-20"
    assert N.normalize_date("today", now) == "2026-06-19"
    assert N.normalize_date("yesterday", now) == "2026-06-18"


def test_date_components_present():
    assert N.date_components_present("1990-01-01", "my birthday is January first nineteen ninety")
    assert N.date_components_present("1990-01-01", "born on 1 january 1990")
    assert not N.date_components_present("1990-01-01", "I have no idea")


def test_phones():
    assert N.normalize_phone("(555) 123-4567") == "5551234567"
    assert N.normalize_phone("five five five one two three") == "555123"
    assert N.phones_match("+1 555 123 4567", "5551234567")
    assert not N.phones_match("5551234567", "9998887777")
