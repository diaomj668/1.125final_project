"""Plan, check, and rebuild.

1. The planner builds a one-day itinerary.
2. The checker verifies it against the raw records.
3. If a stop fails, that place is excluded and the plan is rebuilt.
The loop stops after max_attempts. The log records every attempt, so the
checker output can be shown to the user.
"""
from dataclasses import dataclass, field, replace

from .checker import check_itinerary
from .planner import DAYS, build_plan
from .optimizer import improve_route


@dataclass
class PlanResult:
    itinerary: object                      # Itinerary or None
    attempts: list = field(default_factory=list)  # one dict per attempt
    excluded: frozenset = frozenset()


def trip_days(start_day, n_days):
    """Consecutive weekday names starting at start_day, wrapping after Sunday."""
    i = DAYS.index(start_day)
    return [DAYS[(i + k) % len(DAYS)] for k in range(n_days)]


def plan_trip(businesses, catalog, req, n_days, max_attempts=5, router=None):
    """Plan n_days in a row, starting on req.day. Each day uses req.budget and
    req.max_stops. A place is used at most once across the whole trip.
    Returns a list of (day, PlanResult)."""
    used = set()
    out = []
    for offset, day in enumerate(trip_days(req.day, n_days)):
        from datetime import date, timedelta
        trip_date = (date.fromisoformat(req.trip_date) + timedelta(days=offset)).isoformat() if req.trip_date else None
        result = plan_with_checks(businesses, catalog, replace(req, day=day, trip_date=trip_date),
                                  max_attempts=max_attempts, initial_exclude=frozenset(used), router=router)
        out.append((day, result))
        if result.itinerary is not None:
            used |= {s.business.gmap_id for s in result.itinerary.stops}
    return out


def plan_with_checks(businesses, catalog, req, max_attempts=5, initial_exclude=frozenset(), router=None):
    excluded = set(initial_exclude)
    attempts = []
    for n in range(1, max_attempts + 1):
        itin = build_plan(businesses, req, exclude=frozenset(excluded), router=router)
        if not itin.stops:
            attempts.append({"attempt": n, "stops": 0, "violations": [],
                             "note": "no feasible stops with these constraints"})
            break
        itin = improve_route(itin, router)
        violations = check_itinerary(itin, catalog, router)
        attempts.append({"attempt": n, "stops": len(itin.stops), "violations": violations})
        if not violations:
            return PlanResult(itin, attempts, frozenset(excluded))
        bad = {itin.stops[v.stop_index].business.gmap_id
               for v in violations if v.stop_index is not None}
        if not bad:  # a whole-plan failure (e.g. budget) cannot be fixed by swapping stops
            break
        excluded |= bad
    return PlanResult(None, attempts, frozenset(excluded))
