"""Independent checker: re-verifies an itinerary against the raw records.

It does not trust the planner. For every stop it looks up the record by
gmap_id, re-parses the recorded hours for the trip day, and checks:
  record_exists  the stop's place is in the loaded data
  traceability   the stop's link matches the record
  duplicate      no place is visited twice
  hours_unknown  the record has no hours for that day
  open_hours     the whole visit fits inside recorded opening hours
  within_day     the plan starts and ends inside the requested day window
  duration       visit length matches the interest's standard length
  travel_time    the traveler has time to reach the stop from the previous one
  budget         estimated total cost is within budget
"""
import math
from dataclasses import dataclass
from typing import Optional

from .geo import travel_minutes
from .hours import is_open, parse_day_hours
from .interests import visit_minutes
from .planner import estimate_cost


@dataclass(frozen=True)
class Violation:
    stop_index: Optional[int]
    rule: str
    message: str


def check_itinerary(itin, catalog):
    """catalog: dict gmap_id -> Business. Returns a list of Violation (empty = pass)."""
    req = itin.request
    out = []
    seen = set()
    prev = None
    total = 0.0

    for i, s in enumerate(itin.stops):
        b = catalog.get(s.business.gmap_id)
        if b is None:
            out.append(Violation(i, "record_exists", f"{s.business.name!r} is not in the data"))
            prev = s
            continue
        if b.gmap_id in seen:
            out.append(Violation(i, "duplicate", f"{b.name!r} is visited twice"))
        seen.add(b.gmap_id)

        if s.business.url != b.url:
            out.append(Violation(i, "traceability", f"link for {b.name!r} does not match the record"))

        if s.start_min < req.start_min or s.end_min > req.end_min:
            out.append(Violation(i, "within_day", f"{b.name!r} is outside the day window"))

        if s.end_min - s.start_min != visit_minutes(s.interest):
            out.append(Violation(i, "duration", f"{b.name!r} visit length is wrong"))

        parsed = parse_day_hours(b.hours.get(req.day))
        if parsed is None:
            out.append(Violation(i, "hours_unknown", f"no recorded hours for {b.name!r} on {req.day}"))
        elif not is_open(parsed, s.start_min, s.end_min):
            out.append(Violation(i, "open_hours", f"{b.name!r} is not open for the whole visit"))

        if prev is None:
            origin, depart = req.anchor, req.start_min
        else:
            origin, depart = (prev.business.lat, prev.business.lon), prev.end_min
        needed = math.ceil(travel_minutes(origin[0], origin[1], b.lat, b.lon))
        if s.start_min < depart + needed:
            out.append(Violation(i, "travel_time",
                                 f"not enough travel time to reach {b.name!r}"))

        cost, _ = estimate_cost(b)
        total += cost
        prev = s

    if total > req.budget:
        out.append(Violation(None, "budget",
                             f"estimated total ${total:.0f} is over budget ${req.budget:.0f}"))
    return out
