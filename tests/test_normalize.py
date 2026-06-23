"""Unit tests for the normalization layer (_matching/normalize.py).

Every test here exercises a single normalizer function in isolation —
no transcripts, no policies, no decorators.
"""

from __future__ import annotations

from datetime import date

from saidso._matching import normalize as N

# --------------------------------------------------------------------------- #
# words_to_int
# --------------------------------------------------------------------------- #


def test_words_to_int_common_forms():
    assert N.words_to_int("forty two") == 42
    assert N.words_to_int("two thousand five") == 2005
    assert N.words_to_int("one hundred twenty three") == 123
    assert N.words_to_int("zero") == 0
    assert N.words_to_int("banana") is None


def test_words_to_int_edge_cases():
    assert N.words_to_int("") is None
    assert N.words_to_int("definitely not a number") is None
    assert N.words_to_int("two thousand and twelve") == 2012   # "and" connector
    assert N.words_to_int("five thousand") == 5000


# --------------------------------------------------------------------------- #
# find_numbers / find_years
# --------------------------------------------------------------------------- #


def test_find_numbers():
    assert N.find_numbers("") == set()
    assert 1234 in N.find_numbers("the code is 1,234")
    assert 42 in N.find_numbers("she said forty two")


def test_find_years():
    assert 1990 in N.find_years("nineteen ninety")
    assert 1984 in N.find_years("nineteen eighty four")
    assert 2005 in N.find_years("two thousand five")
    assert 2024 in N.find_years("twenty twenty four")
    assert 1990 in N.find_years("born in 1990")
    assert 2020 in N.find_years("the year twenty twenty")
    assert 2012 in N.find_years("born two thousand and twelve")
    assert 2000 in N.find_years("the year two thousand")


# --------------------------------------------------------------------------- #
# normalize_date
# --------------------------------------------------------------------------- #


def test_normalize_date_iso_and_textual():
    assert N.normalize_date("1990-01-01") == "1990-01-01"
    assert N.normalize_date("January 1, 1990") == "1990-01-01"
    assert N.normalize_date("1 January 1990") == "1990-01-01"
    assert N.normalize_date("January first, nineteen ninety") == "1990-01-01"
    assert N.normalize_date("3/14/1990") == "1990-03-14"
    assert N.normalize_date("3/5/2026") == "2026-03-05"


def test_normalize_date_relative():
    now = date(2026, 6, 19)
    assert N.normalize_date("tomorrow", now) == "2026-06-20"
    assert N.normalize_date("today", now) == "2026-06-19"
    assert N.normalize_date("yesterday", now) == "2026-06-18"


def test_normalize_date_invalid():
    assert N.normalize_date("not a date") is None
    assert N.normalize_date("February 30 2020") is None  # impossible calendar date


# --------------------------------------------------------------------------- #
# date_components_present
# --------------------------------------------------------------------------- #


def test_date_components_present():
    assert N.date_components_present("1990-01-01", "my birthday is January first nineteen ninety")
    assert N.date_components_present("1990-01-01", "born on 1 january 1990")
    assert N.date_components_present("1990-01-01", "january first nineteen ninety")
    assert not N.date_components_present("1990-01-01", "I have no idea")


# --------------------------------------------------------------------------- #
# Phone normalization
# --------------------------------------------------------------------------- #


def test_phones():
    assert N.normalize_phone("(555) 123-4567") == "5551234567"
    assert N.normalize_phone("five five five one two three") == "555123"
    assert N.normalize_phone("five five five one two three four") == "5551234"
    assert N.normalize_phone("") == ""
    assert N.phones_match("+1 555 123 4567", "5551234567")
    assert not N.phones_match("5551234567", "9998887777")
