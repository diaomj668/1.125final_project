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
  travel_time    the traveler has time to reach the stop from the previous one (road time)
  budget         estimated total cost is within budget
"""
from dataclasses import dataclass
from typing import Optional

from .data import address_city
from .geo import haversine_km
from .hours import is_open, parse_day_hours
from .interests import visit_minutes, meal_options, interests_for
from .planner import estimate_cost, travel_lookup


@dataclass(frozen=True)
class Violation:
    stop_index: Optional[int]
    rule: str
    message: str


def check_itinerary(itin, catalog, router=None):
    """catalog: dict gmap_id -> Business. Returns a list of Violation (empty = pass).
    router: same Router the planner used (road times); None = straight-line."""
    req = itin.request
    out = []
    seen = set()
    used_meals = set()
    prev = None
    total = 0.0

    for i, s in enumerate(itin.stops):
        b = catalog.get(s.business.gmap_id)
        if b is None:
            out.append(Violation(i, "record_exists", f"{s.business.name!r} is not in the data"))
            prev = s
            continue
        if req.scope_city and address_city(b.address).casefold() != req.scope_city.casefold():
            out.append(Violation(i, "city_scope", f"{b.name!r} is outside {req.scope_city}"))
        if s.interest not in interests_for(b, req.interests):
            out.append(Violation(i, "interest", "Stop does not match requested interests"))
        if haversine_km(*req.anchor, b.lat, b.lon) > req.radius_km:
            out.append(Violation(i, "radius", "Stop is outside the search radius"))
        if b.rating < req.min_rating or b.n_reviews < req.min_reviews:
            out.append(Violation(i, "quality", "Stop fails the dataset quality threshold"))
        if s.interest == "food" and not s.meal:
            out.append(Violation(i, "meal_time", "Food stop has no meal type"))
        if s.interest == "food" and s.meal:
            valid = any(name == s.meal and opening <= s.start_min and s.end_min <= closing for name, opening, closing in meal_options(b, used_meals))
            if not valid:
                out.append(Violation(i, "meal_time", "Meal type, time or repetition is invalid"))
            used_meals.add(s.meal)
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
        needed = travel_lookup(router, origin, [(b.lat, b.lon)], depart, req.trip_date)[0][0]
        if req.max_leg_min is not None and needed > req.max_leg_min:
            out.append(Violation(i, "leg_limit", f"travel to {b.name!r} exceeds {req.max_leg_min} minutes"))
        if s.start_min < depart + needed:
            out.append(Violation(i, "travel_time",
                                 f"not enough travel time to reach {b.name!r}"))

        cost, _ = estimate_cost(b)
        if s.cost != cost:
            out.append(Violation(i, "cost", "Displayed cost differs from dataset estimate"))
        total += cost
        prev = s

    if req.end_point and prev is not None:
        back = travel_lookup(router, (prev.business.lat, prev.business.lon), [req.end_point], prev.end_min, req.trip_date)[0][0]
        if prev.end_min + back > req.end_min:
            out.append(Violation(len(itin.stops) - 1, "end_leg",
                                 "not enough time to reach the end point before the day ends"))
    if len(itin.stops) > req.max_stops:
        out.append(Violation(None, "max_stops", "Too many stops"))
    if total > req.budget:
        out.append(Violation(None, "budget",
                             f"estimated total ${total:.0f} is over budget ${req.budget:.0f}"))
    return out
