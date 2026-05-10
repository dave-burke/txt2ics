#!/usr/bin/env python3
"""
Convert a flat text file to an .ics calendar file for Google Calendar import.

Input format (one event per line):
  Timed event:
    2026-05-15T09:00:00 2026-05-15T10:00:00 | Team standup | Conference Room A

  All-day / multi-day event (date only, no time):
    2026-01-01 2026-01-01 | New Year's Day | optional location
    2026-01-01 2026-01-03 | Multi-day event

  Blank lines and lines starting with # are ignored.

Usage:
  python3 txt_to_ics.py input.txt output.ics
"""

import sys
import uuid
from datetime import datetime, timezone


def parse_dt(s: str) -> tuple[str, bool]:
    """
    Parse an ISO date or datetime string.
    Returns (ical_string, is_all_day).
    - Date-only input  -> ("20260101",        True)
    - Datetime input   -> ("20260101T090000", False)
    """
    s = s.strip()
    all_day = "T" not in s
    try:
        if all_day:
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%Y%m%d"), True
        else:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%Y%m%dT%H%M%S"), False
    except ValueError as e:
        raise ValueError(f"Cannot parse '{s}': {e}")


def convert(input_path: str, output_path: str):
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
                    f"Line {lineno}: skipping — expected at least one '|' separator",
                    file=sys.stderr,
                )
                continue

            date_tokens = parts[0].split()
            if len(date_tokens) != 2:
                print(
                    f"Line {lineno}: skipping — expected 2 datetimes before '|', got {len(date_tokens)}",
                    file=sys.stderr,
                )
                continue

            summary = parts[1]
            location = parts[2] if len(parts) >= 3 else None

            try:
                dtstart, start_all_day = parse_dt(date_tokens[0])
                dtend, end_all_day = parse_dt(date_tokens[1])
            except ValueError as e:
                print(f"Line {lineno}: skipping — {e}", file=sys.stderr)
                continue

            if start_all_day != end_all_day:
                print(
                    f"Line {lineno}: skipping — start and end must both be dates or both be datetimes",
                    file=sys.stderr,
                )
                continue

            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{uuid.uuid4()}@ics-converter")
            lines.append(f"DTSTAMP:{now}")

            if start_all_day:
                lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
                lines.append(f"DTEND;VALUE=DATE:{dtend}")
            else:
                lines.append(f"DTSTART:{dtstart}")
                lines.append(f"DTEND:{dtend}")

            lines.append(f"SUMMARY:{summary}")
            if location:
                lines.append(f"LOCATION:{location}")
            lines.append("END:VEVENT")
            events_written += 1

    lines.append("END:VCALENDAR")

    with open(output_path, "w", newline="\r\n") as f:
        f.write("\r\n".join(lines) + "\r\n")

    print(f"Done — {events_written} event(s) written to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input.txt output.ics")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
