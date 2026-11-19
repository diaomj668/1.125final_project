"""Parse Google Local opening-hours text such as "5:30AM–1PM" into minutes.

Parsed form (what the rest of the code uses):
    None        -> hours not recorded for that weekday (unknown)
    "closed"    -> the record says Closed
    "always"    -> the record says Open 24 hours
    [(open, close), ...] -> list of intervals in minutes since midnight.
                            close may exceed 1440 for places open past midnight.
"""
import re

_CLOCK_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\s*$", re.IGNORECASE)
_DASH_RE = re.compile(r"\s*[–—-]\s*")  # en dash, em dash, or hyphen


def parse_clock(text):
    """'5:30AM' -> 330, '1PM' -> 780. Returns None if it is not a clock time."""
    m = _CLOCK_RE.match(text)
    if not m:
        return None
    raw_hour = int(m.group(1))
    if not 1 <= raw_hour <= 12:
        return None
    hour = raw_hour % 12
    minute = int(m.group(2) or 0)
    if hour > 12 or minute > 59:
        return None
    if m.group(3).upper() == "PM":
        hour += 12
    return hour * 60 + minute


def parse_day_hours(text):
    """Parse one weekday's hours text from the metadata file."""
    if text is None:
        return None
    raw = text.strip()
    if raw.lower() == "closed":
        return "closed"
    if raw.lower() == "open 24 hours":
        return "always"
    intervals = []
    for piece in raw.split(","):
        bits = _DASH_RE.split(piece.strip())
        if len(bits) != 2:
            return None
        # Infer a missing meridiem only when both endpoints clearly share it,
        # or noon is the start (e.g. 12–5PM). Do not guess ambiguous 9–5PM.
        left, right = bits[0], bits[1]
        if not re.search(r"[AP]M", left, re.I) and re.search(r"[AP]M", right, re.I):
            match = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*", left)
            right_match = _CLOCK_RE.match(right)
            if match and right_match:
                lh, rh = int(match[1]), int(right_match[1])
                suffix = right_match[3].upper()
                if (lh <= rh and lh != 12) or (lh == 12 and suffix == "PM"):
                    left += suffix
        opens, closes = parse_clock(left), parse_clock(right)
        if opens is None or closes is None:
            return None
        if closes <= opens:  # e.g. 6PM–2AM closes after midnight
            closes += 24 * 60
        intervals.append((opens, closes))
    return intervals or None


def is_open(parsed, start, end):
    """True only if the whole visit [start, end] fits inside opening hours."""
    if parsed == "always":
        return True
    if parsed is None or parsed == "closed":
        return False
    return any(o <= start and end <= c for o, c in parsed)


def earliest_start(parsed, arrival, duration):
    """Earliest visit start >= arrival that finishes before closing, or None."""
    if parsed == "always":
        return arrival
    if parsed is None or parsed == "closed":
        return None
    for o, c in sorted(parsed):
        start = max(arrival, o)
        if start + duration <= c:
            return start
    return None
