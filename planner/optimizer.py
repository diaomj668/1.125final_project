"""Bounded route improvement. Never accepts an infeasible or slower reordering."""
from dataclasses import replace
import math
from .geo import haversine_km
from .hours import earliest_start, parse_day_hours
from .interests import meal_options, visit_minutes
from .planner import Itinerary, travel_lookup


def schedule(order, req, router):
    origin, depart = req.anchor, req.start_min
    stops, meals = [], set()
    for old in order:
        b = old.business
        travel, source = travel_lookup(router, origin, [(b.lat, b.lon)], depart, req.trip_date)[0]
        if not math.isfinite(travel) or (req.max_leg_min is not None and travel > req.max_leg_min):
            return None
        arrival = depart + travel
        parsed = parse_day_hours(b.hours.get(req.day))
        duration = visit_minutes(old.interest)
        if old.interest == 'food':
            window = next(((lo, hi) for name, lo, hi in meal_options(b, meals) if name == old.meal), None)
            if not window: return None
            start = earliest_start(parsed, max(arrival, window[0]), duration)
            if start is None or start + duration > window[1]: return None
            meals.add(old.meal)
        else:
            start = earliest_start(parsed, arrival, duration)
        if start is None or start + duration > req.end_min: return None
        stops.append(replace(old, arrival_min=arrival, start_min=start, end_min=start+duration,
                             travel_min=travel, travel_source=source))
        origin, depart = (b.lat, b.lon), start+duration
    if req.end_point:
        back = travel_lookup(router, origin, [req.end_point], depart, req.trip_date)[0][0]
        if not math.isfinite(back) or depart + back > req.end_min: return None
    return Itinerary(req, stops)


def metrics(itinerary, router):
    req = itinerary.request
    travel = sum(s.travel_min for s in itinerary.stops)
    wait = sum(s.start_min-s.arrival_min for s in itinerary.stops)
    if req.end_point and itinerary.stops:
        last = itinerary.stops[-1]
        travel += travel_lookup(router, (last.business.lat,last.business.lon), [req.end_point], last.end_min, req.trip_date)[0][0]
    return travel, wait


def geometric_length(order, req):
    points = [req.anchor] + [(s.business.lat,s.business.lon) for s in order]
    if req.end_point: points.append(req.end_point)
    return sum(haversine_km(*a,*b) for a,b in zip(points,points[1:]))


def improve_route(itinerary, router=None, max_trials=6):
    """Try promising reversals within meal-separated sightseeing blocks.

    Meals keep their position and meal identity. Candidate orders are rescheduled
    with directed, departure-time-aware travel and checked before acceptance.
    This is a local improvement, not a globally optimal route solver.
    """
    from .checker import check_itinerary
    if len(itinerary.stops)<3: return itinerary
    best=itinerary
    catalog={s.business.gmap_id:s.business for s in itinerary.stops}
    for _ in range(2):
        original=best.stops
        base_geo=geometric_length(original,best.request)
        candidates=[]
        for i in range(len(original)-1):
            for j in range(i+1,len(original)):
                if any(s.interest=='food' for s in original[i:j+1]): break
                order=original[:i]+list(reversed(original[i:j+1]))+original[j+1:]
                length=geometric_length(order,best.request)
                if length+0.01<base_geo:
                    candidates.append((length,i,j,order))
        if not candidates: break
        before=best
        before_travel,before_wait=metrics(best,router)
        best_quality=(before_travel+before_wait*.25,before_travel)
        for _,_,_,order in sorted(candidates,key=lambda x:x[:3])[:max_trials]:
            candidate=schedule(order,best.request,router)
            if candidate is None: continue
            travel,wait=metrics(candidate,router)
            quality=(travel+wait*.25,travel)
            if travel<before_travel and quality<best_quality and not check_itinerary(candidate,catalog,router):
                best,best_quality=candidate,quality
        if best is before: break
    return best
