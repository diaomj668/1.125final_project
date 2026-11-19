"""Build a one-day itinerary with a greedy, constraint-aware search.

The planner only uses places whose recorded hours cover the visit, so most
checks pass by construction. The independent checker (checker.py) re-verifies
the final plan from the raw records.

Travel times come from a Router (road driving times). Without a router, the
straight-line estimate is used.
"""
import math
from dataclasses import dataclass, field

from .data import Business, address_city
from .geo import haversine_km, travel_minutes
from .hours import earliest_start, parse_day_hours
from .interests import interests_for, visit_minutes, meal_options

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PRICE_ESTIMATE = {"$": 12, "$$": 25, "$$$": 50, "$$$$": 90}  # USD per person, estimates
MISSING_PRICE_ESTIMATE = 15
BOSTON_ANCHOR = (42.3601, -71.0589)  # Boston Common; override with --anchor
SHORTLIST = 25  # candidates per step that get a road-time lookup


@dataclass(frozen=True)
class Request:
    day: str
    interests: tuple
    budget: float                 # estimated spend for the day, USD per person
    start_min: int = 10 * 60
    end_min: int = 20 * 60
    max_stops: int = 4
    anchor: tuple = BOSTON_ANCHOR
    radius_km: float = 20.0
    min_rating: float = 4.0
    min_reviews: int = 5
    travel_mode: str = "driving"
    trip_date: str = None
    scope_city: str = ""
    max_leg_min: int = None
    end_point: tuple = None      # optional (lat, lon); the day must end with a drive there


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
    travel_source: str = "straight-line"  # 'road' or 'straight-line'
    meal: str = ""


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


def travel_lookup(router, origin, dest_list, depart_min=0, trip_date=None):
    """(minutes, source) for each (lat, lon) in dest_list, from origin."""
    if router is None:
        return [(math.ceil(travel_minutes(origin[0], origin[1], la, lo)), "straight-line")
                for la, lo in dest_list]
    if hasattr(router, "minutes_at"):
        return router.minutes_at(origin, dest_list, depart_min, trip_date)
    return router.minutes(origin, dest_list)



def recommendation_score(business, distance_km):
    """Popularity with diminishing returns, quality, visitor relevance and travel effort."""
    categories = {c.casefold() for c in business.categories}
    generic_retail = {"department store", "discount store", "supermarket", "grocery store", "warehouse store"}
    visitor_retail = {"gift shop", "souvenir store", "antique store", "book store", "craft store"}
    relevance = -2.0 if categories & generic_retail else 0.0
    if categories & visitor_retail:
        relevance += 0.5
    return math.log1p(business.n_reviews) + 2 * (business.rating - 4) + relevance - 0.8 * distance_km

def build_plan(businesses, req, exclude=frozenset(), router=None):
    if req.day not in DAYS:
        raise ValueError(f"unknown day: {req.day}")
    if not req.interests:
        raise ValueError("at least one interest is required")

    # Candidate pool: dataset only, rating/review quality, known hours, within radius.
    pool = []
    for b in businesses:
        if req.scope_city and address_city(b.address).casefold() != req.scope_city.casefold():
            continue
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
    used_meals = set()

    while len(stops) < req.max_stops:
        # Rank only dataset records by review count, then rating and distance.
        cands = []
        for b, matched, parsed in pool:
            if b.gmap_id in used:
                continue
            open_interests = [i for i in matched if (i == "food" and len(used_meals) < 3) or (i != "food" and counts[i] < cap)]
            if not open_interests:
                continue
            interest = min(open_interests, key=lambda i: counts[i])
            if interest == "food" and not any(close >= cur_time + 60 and opening + 60 <= req.end_min for _, opening, close in meal_options(b, used_meals)):
                continue
            cost, _ = estimate_cost(b)
            if spent + cost > req.budget:
                continue
            earliest = earliest_start(parsed, cur_time, visit_minutes(interest))
            if earliest is None or earliest + visit_minutes(interest) > req.end_min:
                continue
            km = haversine_km(cur_loc[0], cur_loc[1], b.lat, b.lon)
            cands.append((km, b.gmap_id, b, interest, parsed))
        if not cands:
            break
        def meal_priority(candidate):
            if candidate[3] != "food": return 1
            return 0 if any(opening - 30 <= cur_time <= closing - 60 for _, opening, closing in meal_options(candidate[2], used_meals)) else 2
        cands.sort(key=lambda c: (meal_priority(c), -recommendation_score(c[2], c[0]), -c[2].n_reviews, c[1]))
        batch_size = getattr(router, "shortlist_limit", SHORTLIST)
        best = None
        # Stop after the first feasible popularity batch; avoid routing the whole catalog.
        for offset in range(0, len(cands), batch_size):
            shortlist = cands[offset:offset + batch_size]
            times = travel_lookup(router, cur_loc, [(c[2].lat, c[2].lon) for c in shortlist], cur_time, req.trip_date)
            for idx, ((km, _, b, interest, parsed), (travel, tsrc)) in enumerate(zip(shortlist, times)):
                if not math.isfinite(travel) or (req.max_leg_min is not None and travel > req.max_leg_min):
                    continue
                arrival = cur_time + travel
                duration = visit_minutes(interest)
                meal = ""
                if interest == "food":
                    options = []
                    for name, opening, closing in meal_options(b, used_meals):
                        candidate_start = earliest_start(parsed, max(arrival, opening), duration)
                        if candidate_start is not None and candidate_start + duration <= min(closing, req.end_min):
                            options.append((candidate_start, name))
                    if not options: continue
                    start, meal = min(options)
                else:
                    start = earliest_start(parsed, arrival, duration)
                if start is None:
                    continue
                end = start + duration
                if end > req.end_min:
                    continue
                if req.end_point:
                    back = travel_lookup(router, (b.lat, b.lon), [req.end_point], end, req.trip_date)[0][0]
                    if end + back > req.end_min:
                        continue
                cost, source = estimate_cost(b)
                if spent + cost > req.budget:
                    continue
                key = (0 if meal and start <= cur_time + 30 else 1 if not meal else 2, -(recommendation_score(b, km) - 0.04 * travel - 0.015 * (start-arrival)), start - cur_time, -b.n_reviews, b.gmap_id)
                if best is None or key < best[0]:
                    best = (key, b, interest, arrival, start, end, travel, tsrc, cost, source, meal)

            if best is not None:
                break

        if best is None:
            break
        _, b, interest, arrival, start, end, travel, tsrc, cost, source, meal = best
        stops.append(Stop(b, interest, arrival, start, end, travel, cost, source, tsrc, meal))
        if meal: used_meals.add(meal)
        used.add(b.gmap_id)
        counts[interest] += 1
        spent += cost
        cur_loc = (b.lat, b.lon)
        cur_time = end

    return Itinerary(req, stops)
