"""What `--expires` means, pinned.

The vendor types this once and a shop lives by it for a year, so every
accepted form is written down here rather than left to whatever
`fromisoformat` happens to allow. The one that matters most is the bare
date: it is the form a licence is actually sold in ("expires 13 August"),
and reading it as midnight would silently take a day off every licence
issued that way.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from scripts.licensing.issue_license import parse_expiry


def test_no_expiry_at_all_is_a_perpetual_licence():
    assert parse_expiry("") is None
    assert parse_expiry("   ") is None


@pytest.mark.parametrize("written", ["2027-08-13", "13-08-2027"])
def test_a_date_on_its_own_covers_the_whole_of_that_day(written: str):
    """Both the way a computer writes it and the way this shop does."""
    assert parse_expiry(written) == datetime(2027, 8, 13, 23, 59, 59)


@pytest.mark.parametrize(
    "written",
    [
        "2027-08-13T03:45:56",
        "2027-08-13 03:45:56",
        "13-08-2027 03:45:56",
    ],
)
def test_a_time_that_was_named_is_the_time_that_is_signed(written: str):
    assert parse_expiry(written) == datetime(2027, 8, 13, 3, 45, 56)


def test_the_seconds_may_be_left_off():
    assert parse_expiry("13-08-2027 03:45") == datetime(2027, 8, 13, 3, 45)


def test_a_timestamp_carrying_an_offset_is_converted_to_pkt():
    """The app compares against a naive PKT clock, so a licence issued
    from a machine in another timezone must land on that one."""
    # 03:45 UTC is 08:45 in PKT (UTC+5).
    assert parse_expiry("2027-08-13T03:45:00+00:00") == datetime(2027, 8, 13, 8, 45)


@pytest.mark.parametrize("written", ["next tuesday", "13/08/2027", "2027-13-45"])
def test_something_that_is_not_a_date_is_refused_by_name(written: str):
    with pytest.raises(ValueError, match="--expires"):
        parse_expiry(written)
