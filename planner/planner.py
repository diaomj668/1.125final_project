"""Build a one-day itinerary with a greedy, constraint-aware search.

The planner only uses places whose recorded hours cover the visit, so most
checks pass by construction. The independent checker (checker.py) re-verifies
the final plan from the raw records.
"""
import math
from dataclasses import dataclass, field

from .geo import haversine_km, travel_minutes
from .hours import earliest_start, parse_day_hours
from .interests import interests_for, visit_minutes
from .data import Business

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PRICE_ESTIMATE = {"$": 12, "$$": 25, "$$$": 50, "$$$$": 90}  # USD per person, estimates
MISSING_PRICE_ESTIMATE = 15
BOSTON_ANCHOR = (42.3601, -71.0589)  # Boston Common; override with --anchor


@dataclass(frozen=True)
class Request:
    day: str
    interests: tuple
    budget: float                 # total estimated spend, USD per person
    start_min: int = 10 * 60
    end_min: int = 20 * 60
    max_stops: int = 4
    anchor: tuple = BOSTON_ANCHOR
    radius_km: float = 20.0
    min_rating: float = 4.0
    min_reviews: int = 5


@dataclass(frozen=True)
class Stop:
    business: Business
    interest: str
    arrival_min: int   # when the traveler arrives
    start_min: int     # visit start (later than arrival if waiting for opening)
    end_min: int
    travel_min: int    # travel from the previous stop (or the anchor)
    cost: float
    cost_source: str


@dataclass
class Itinerary:
    request: Request
    stops: list = field(default_factory=list)

    @property
    def total_cost(self):
        return sum(s.cost for s in self.stops)


def estimate_cost(b):
    if b.price in PRICE_ESTIMATE:
        return PRICE_ESTIMATE[b.price], f"price tier {b.price} (estimate)"
    return MISSING_PRICE_ESTIMATE, "no price recorded (default estimate)"


def build_plan(businesses, req, exclude=frozenset()):
    if req.day not in DAYS:
        raise ValueError(f"unknown day: {req.day}")
    if not req.interests:
        raise ValueError("at least one interest is required")

    # Candidate pool: quality filter, hours known for the day, within radius.
    pool = []
    for b in businesses:
        if b.gmap_id in exclude:
            continue
        if b.rating < req.min_rating or b.n_reviews < req.min_reviews:
            continue
        matched = interests_for(b, req.interests)
        if not matched:
            continue
        parsed = parse_day_hours(b.hours.get(req.day))
        if parsed is None:  # hours not recorded: do not plan a stop we cannot verify
            continue
        if haversine_km(req.anchor[0], req.anchor[1], b.lat, b.lon) > req.radius_km:
            continue
        pool.append((b, matched, parsed))

    stops = []
    spent = 0.0
    cur_loc = req.anchor
    cur_time = req.start_min
    counts = {i: 0 for i in req.interests}
    cap = math.ceil(req.max_stops / len(req.interests))  # spread stops across interests
    used = set()

    while len(stops) < req.max_stops:
        best = None
        for b, matched, parsed in pool:
            if b.gmap_id in used:
                continue
            open_interests = [i for i in matched if counts[i] < cap]
            if not open_interests:
                continue
            interest = min(open_interests, key=lambda i: counts[i])
            travel = math.ceil(travel_minutes(cur_loc[0], cur_loc[1], b.lat, b.lon))
            arrival = cur_time + travel
            duration = visit_minutes(interest)
            start = earliest_start(parsed, arrival, duration)
            if start is None:
                continue
            end = start + duration
            if end > req.end_min:
                continue
            cost, source = estimate_cost(b)
            if spent + cost > req.budget:
                continue
            key = (start - cur_time, -b.rating, -b.n_reviews, b.gmap_id)
            if best is None or key < best[0]:
                best = (key, b, interest, arrival, start, end, travel, cost, source)

        if best is None:
            break
        _, b, interest, arrival, start, end, travel, cost, source = best
        stops.append(Stop(b, interest, arrival, start, end, travel, cost, source))
        used.add(b.gmap_id)
        counts[interest] += 1
        spent += cost
        cur_loc = (b.lat, b.lon)
        cur_time = end

    return Itinerary(req, stops)
