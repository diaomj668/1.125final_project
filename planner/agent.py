"""Plan, check, and rebuild.

1. The planner builds a one-day itinerary.
2. The checker verifies it against the raw records.
3. If a stop fails, that place is excluded and the plan is rebuilt.
The loop stops after max_attempts. The log records every attempt, so the
checker output can be shown to the user.
"""
from dataclasses import dataclass, field

from .checker import check_itinerary
from .planner import build_plan


@dataclass
class PlanResult:
    itinerary: object                      # Itinerary or None
    attempts: list = field(default_factory=list)  # one dict per attempt
    excluded: frozenset = frozenset()


def plan_with_checks(businesses, catalog, req, max_attempts=5):
    excluded = set()
    attempts = []
    for n in range(1, max_attempts + 1):
        itin = build_plan(businesses, req, exclude=frozenset(excluded))
        if not itin.stops:
            attempts.append({"attempt": n, "stops": 0, "violations": [],
                             "note": "no feasible stops with these constraints"})
            break
        violations = check_itinerary(itin, catalog)
        attempts.append({"attempt": n, "stops": len(itin.stops), "violations": violations})
        if not violations:
            return PlanResult(itin, attempts, frozenset(excluded))
        bad = {itin.stops[v.stop_index].business.gmap_id
               for v in violations if v.stop_index is not None}
        if not bad:  # a whole-plan failure (e.g. budget) cannot be fixed by swapping stops
            break
        excluded |= bad
    return PlanResult(None, attempts, frozenset(excluded))
