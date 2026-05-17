#!/usr/bin/env python3
"""
Convert a flat text file to an .ics calendar file for Google Calendar import.

Flexible input formats (one event per line):

  Full datetime, both sides:
    2026-05-01T08:00:00 2026-05-01T09:00:00 | description | optional location

  Seconds optional:
    2026-05-01T08:00 2026-05-01T09:00 | description

  End time only (inherits date from start):
    2026-05-01T08:00 9:00 | description

  Year optional (assumed current year):
    05-01T08:00 9:00 | description

  Space instead of T between date and time (3 tokens):
    05-01 08:00 9:00 | description
    2026-05-01 08:00 9:00 | description

  All-day / multi-day (date only, no time):
    2026-05-01 2026-05-01 | description
    2026-05-01 2026-05-03 | multi-day

  Hours are never required to be zero-padded (9:00 and 09:00 both work).
  Blank lines and lines starting with # are ignored.

Usage:
  python3 txt_to_ics.py input.txt output.ics
"""

import re
import sys
import uuid
from datetime import date, datetime, timezone

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_DATE_RE = re.compile(r"^(?:(\d{4})-)?(\d{2})-(\d{2})$")
_DATETIME_RE = re.compile(
    r"^(?:(\d{4})-)?(\d{2})-(\d{2})T(\d{1,2}):(\d{2})(?::(\d{2}))?$"
)


def _is_time(s):
    return bool(_TIME_RE.match(s))


def _is_date(s):
    return bool(_DATE_RE.match(s))


def _is_datetime(s):
    return bool(_DATETIME_RE.match(s))


def _parse_time(s):
    """'H:MM[:SS]' -> (hour, minute, second)"""
    m = _TIME_RE.match(s)
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def _parse_date(s):
    """'[YYYY-]MM-DD' -> date (current year assumed if omitted)"""
    m = _DATE_RE.match(s)
    year = int(m.group(1)) if m.group(1) else datetime.now().year
    return date(year, int(m.group(2)), int(m.group(3)))


def _parse_datetime(s):
    """'[YYYY-]MM-DDTHH:MM[:SS]' -> datetime (current year assumed if omitted)"""
    m = _DATETIME_RE.match(s)
    year = int(m.group(1)) if m.group(1) else datetime.now().year
    return datetime(
        year,
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)),
        int(m.group(5)),
        int(m.group(6) or 0),
    )


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------


def parse_event_times(tokens):
    """
    Parse 2 or 3 whitespace-split date/time tokens.
    Returns (start, end, all_day).
      - Timed events:   start/end are datetime objects, all_day=False
      - All-day events: start/end are date objects,     all_day=True

    Accepted token patterns:
      2 tokens:
        datetime  datetime   full timed event
        datetime  time       end time only; date inherited from start
        date      date       all-day / multi-day
      3 tokens:
        date  time  time     space used instead of T between date and time
    """

    n = len(tokens)

    # -- 3 tokens: "date start_time end_time" (space instead of T) -----------
    if n == 3:
        d_s, st_s, et_s = tokens
        if not _is_date(d_s):
            raise ValueError(f"Expected a date in first position, got '{d_s}'")
        if not _is_time(st_s) or not _is_time(et_s):
            raise ValueError(
                f"Expected two times in positions 2 and 3, got '{st_s}' '{et_s}'"
            )
        d = _parse_date(d_s)
        sh, sm, ss = _parse_time(st_s)
        eh, em, es = _parse_time(et_s)
        start = datetime(d.year, d.month, d.day, sh, sm, ss)
        end = datetime(d.year, d.month, d.day, eh, em, es)
        return start, end, False

    # -- 2 tokens -------------------------------------------------------------
    if n == 2:
        s0, s1 = tokens

        # datetime start
        if _is_datetime(s0):
            start = _parse_datetime(s0)
            if _is_time(s1):
                # end is time-only; inherit date from start
                h, m, s = _parse_time(s1)
                end = start.replace(hour=h, minute=m, second=s)
            elif _is_datetime(s1):
                end = _parse_datetime(s1)
            else:
                raise ValueError(f"Unrecognised end token '{s1}'")
            return start, end, False

        # date-only start -> must be all-day
        if _is_date(s0):
            if _is_date(s1):
                return _parse_date(s0), _parse_date(s1), True
            raise ValueError(
                f"Start looks like a date-only, but end '{s1}' is not a plain date. "
                f"Did you mean to include a time? Use 'MM-DDTHH:MM' or 'MM-DD HH:MM HH:MM'."
            )

    raise ValueError(f"Expected 2 or 3 date/time tokens before '|', got {n}: {tokens}")


# ---------------------------------------------------------------------------
# iCal formatting helpers
# ---------------------------------------------------------------------------


def _ical_line(dt, all_day, role):
    """role is 'START' or 'END'"""
    if all_day:
        return f"DT{role};VALUE=DATE:{dt.strftime('%Y%m%d')}"
    return f"DT{role}:{dt.strftime('%Y%m%dT%H%M%S')}"


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------


def convert(input_path, output_path):
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    events_written = 0

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ics-converter//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    with open(input_path) as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue

            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 2:
                print(
                    f"Line {lineno}: skipping - no '|' separator found", file=sys.stderr
                )
                continue

            tokens = parts[0].split()
            summary = parts[1]
            location = parts[2] if len(parts) >= 3 else None

            try:
                start, end, all_day = parse_event_times(tokens)
            except ValueError as e:
                print(f"Line {lineno}: skipping - {e}", file=sys.stderr)
                continue

            lines += [
                "BEGIN:VEVENT",
                f"UID:{uuid.uuid4()}@ics-converter",
                f"DTSTAMP:{now}",
                _ical_line(start, all_day, "START"),
                _ical_line(end, all_day, "END"),
                f"SUMMARY:{summary}",
            ]
            if location:
                lines.append(f"LOCATION:{location}")
            lines.append("END:VEVENT")
            events_written += 1

    lines.append("END:VCALENDAR")

    with open(output_path, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")

    print(f"Done - {events_written} event(s) written to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"""Usage: {sys.argv[0]} INPUT OUTPUT

Convert a plain-text event list to an iCalendar (.ics) file.

Arguments:
  INPUT   plain text file, one event per line
  OUTPUT  .ics file to write

Event format:
  START END | SUMMARY [| LOCATION]

START/END formats (most to least explicit):
  2026-05-01T08:00:00   full datetime, seconds optional
  2026-05-01T08:00      date + time (T separator)
  2026-05-01 08:00      date + time (space separator)
  05-01 08:00           date + time, current year assumed
  09:00                 time only; date inherited from START
  2026-05-01            date only; produces an all-day event

Hours need not be zero-padded. Blank lines and # comments are ignored.""")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
