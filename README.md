# txt2ics

Convert a plain text file of events into an `.ics` file that can be imported into Google Calendar (or any other calendar app that supports the iCalendar format).

## Requirements

Python 3.9+. No third-party packages required.

## Usage

```
python3 txt_to_ics.py input.txt output.ics
```

The script prints a count of events written and logs any skipped lines to stderr.

## Input format

One event per line:

```
START END | description
START END | description | location
```

`START` and `END` are date/time values (see formats below). Everything after the first `|` is the event title; an optional second `|` adds a location. Blank lines and lines beginning with `#` are ignored.

### Date and time formats

The input is intentionally flexible. The following are all valid:

```
# Full ISO datetime on both sides
2026-05-01T08:00:00 2026-05-01T09:00:00 | Team standup | Zoom

# Seconds are always optional
2026-05-01T08:00 2026-05-01T09:00 | Team standup

# End time only — date is inherited from the start
2026-05-01T08:00 9:00 | Team standup

# Year optional — current year is assumed when omitted
05-01T08:00 9:00 | Team standup

# Space instead of T between date and time
05-01 08:00 9:00 | Team standup
2026-05-01 08:00 9:00 | Team standup

# All-day event (date only, no time)
2026-05-01 2026-05-01 | Election day

# Multi-day event
2026-12-24 2026-12-26 | Christmas break | Home
```

Rules summary:

- Hours do not need to be zero-padded (`9:00` and `09:00` are both fine).
- If the end value is a time only (e.g. `9:00`), the date is copied from the start.
- If the year is omitted from a date (e.g. `05-01`), the current year is used.
- A space may be used between the date and time instead of `T`.
- If both start and end are plain dates with no time, the event is created as an all-day event.

### Comments and blank lines

```
# This is a comment and will be ignored

2026-06-01 08:00 9:00 | Morning run
```

## Importing into Google Calendar

1. Run the script to produce an `.ics` file.
2. Open [Google Calendar](https://calendar.google.com) in a browser.
3. Click the gear icon → **Settings**.
4. In the left sidebar, click **Import & export**.
5. Under **Import**, choose your `.ics` file and select which calendar to add the events to.
6. Click **Import**.

The same `.ics` file can also be imported into Apple Calendar (File → Import) and Outlook (File → Open & Export → Import/Export).

## Notes

- All times are treated as local (no timezone conversion is performed). Events will appear at the times you wrote, in whichever timezone the destination calendar is set to.
- Event UIDs are randomly generated (UUID4) each time the script runs, so re-importing the same file will create duplicate events rather than updating existing ones.
- The output file uses CRLF line endings as required by the iCalendar spec (RFC 5545).
