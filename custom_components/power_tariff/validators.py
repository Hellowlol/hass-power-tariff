"""Helpers for validate the config."""

import datetime as dt

import voluptuous as vol

DATE_STR_FORMAT = "%d.%m"


def parse_to_date(dt_str):
    """Convert a date string to a date object with with this year."""
    now = dt.datetime.now()
    try:
        return dt.datetime.strptime(dt_str, DATE_STR_FORMAT).date().replace(year=now.year)
    except ValueError:  # If dt_str did not match our format
        return None


def validate_date(dt_str):
    date = parse_to_date(dt_str)
    if date is None:
        vol.Invalid("Failed to parse %s to date, expected format is day.month (01.12")

    return date
