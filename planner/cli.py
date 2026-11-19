"""Command-line entry point.

Examples:
    python -m planner --data data/raw --day Saturday --interests food,culture --budget 80
    python -m planner --data data/raw --day Friday --days 3 --interests food,outdoors
"""
import argparse
import json
import sys
from pathlib import Path

from .agent import plan_trip
from .routing import Router
from .data import load_businesses
from .interests import INTEREST_NAMES
from .planner import BOSTON_ANCHOR, DAYS, Request


def fmt(minutes):
    minutes = int(minutes)
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def parse_clock_arg(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def parse_anchor(text):
    lat, lon = text.split(",")
    return float(lat), float(lon)


def main(argv=None):
    p = argparse.ArgumentParser(description="Massachusetts trip planner with checks (one or more days).")
    p.add_argument("--data", default="data/raw", help="folder with meta-Massachusetts.json.gz")
    p.add_argument("--day", default="Saturday", choices=DAYS, help="first day of the trip")
    p.add_argument("--days", type=int, default=1, help="number of consecutive days (1-7)")
    p.add_argument("--interests", default="food,culture", help="comma list: " + ", ".join(INTEREST_NAMES))
    p.add_argument("--budget", type=float, default=80.0, help="estimated spend per day, USD per person")
    p.add_argument("--start", default="10:00", help="HH:MM, 24h")
    p.add_argument("--end", default="20:00", help="HH:MM, 24h")
    p.add_argument("--max-stops", type=int, default=4, help="stops per day")
    p.add_argument("--anchor", default=f"{BOSTON_ANCHOR[0]},{BOSTON_ANCHOR[1]}", help="lat,lon of the start")
    p.add_argument("--radius-km", type=float, default=20.0)
    p.add_argument("--travel", choices=["road", "straight"], default="road",
                   help="road: driving times from OSRM (cached); straight: straight-line estimate")
    p.add_argument("--json", metavar="PATH", help="also write the trip as JSON")
    args = p.parse_args(argv)

    if not 1 <= args.days <= 7:
        p.error("--days must be between 1 and 7")
    interests = tuple(x.strip() for x in args.interests.split(",") if x.strip())
    bad = [i for i in interests if i not in INTEREST_NAMES]
    if bad:
        p.error(f"unknown interest(s): {bad}; choose from {list(INTEREST_NAMES)}")

    businesses, stats = load_businesses(args.data)
    catalog = {b.gmap_id: b for b in businesses}
    req = Request(day=args.day, interests=interests, budget=args.budget,
                  start_min=parse_clock_arg(args.start), end_min=parse_clock_arg(args.end),
                  max_stops=args.max_stops, anchor=parse_anchor(args.anchor),
                  radius_km=args.radius_km)

    print(f"Data: {stats['kept']} businesses kept "
          f"({stats['permanently_closed']} permanently closed and {stats['out_of_state']} "
          f"out-of-state removed).")
    router = Router(cache_path=Path(args.data).parent / "route_cache.json") if args.travel == "road" else None
    trip = plan_trip(businesses, catalog, req, args.days, router=router)
    if router is not None and router.offline:
        print("Note: road routing server unreachable; straight-line estimates used where no road time is cached.")

    any_failed = False
    total_cost = 0.0
    json_days = []
    for n, (day, result) in enumerate(trip, 1):
        print(f"\n=== Day {n}: {day} · interests: {', '.join(interests)} · budget ${req.budget:.0f} ===")
        print("Checker log:")
        for a in result.attempts:
            if "note" in a:
                print(f"  attempt {a['attempt']}: {a['note']}")
            elif a["violations"]:
                print(f"  attempt {a['attempt']}: {len(a['violations'])} violation(s)")
                for v in a["violations"]:
                    print(f"      - [{v.rule}] {v.message}")
            else:
                print(f"  attempt {a['attempt']}: {a['stops']} stop(s), all checks passed")
        if result.itinerary is None:
            any_failed = True
            print(f"No checked plan for {day}. Try more interests, a bigger budget, or a later end time.")
            json_days.append({"day": day, "stops": []})
            continue

        it = result.itinerary
        total_cost += it.total_cost
        print()
        for k, s in enumerate(it.stops, 1):
            b = s.business
            print(f"{k}. {fmt(s.start_min)}–{fmt(s.end_min)}  {b.name}  [{s.interest}]")
            print(f"     {b.address}")
            print(f"     travel {s.travel_min} min ({s.travel_source}) · est. ${s.cost:.0f} ({s.cost_source})"
                  f" · rating {b.rating} ({b.n_reviews} reviews)")
            print(f"     hours {day}: {b.hours.get(day)}")
            print(f"     record: {b.url}")
        print(f"Estimated day total: ${it.total_cost:.0f} of ${req.budget:.0f} budget")
        json_days.append({
            "day": day,
            "stops": [{
                "name": s.business.name, "gmap_id": s.business.gmap_id, "interest": s.interest,
                "start": fmt(s.start_min), "end": fmt(s.end_min), "travel_min": s.travel_min,
                "cost_estimate": s.cost, "hours": s.business.hours.get(day), "url": s.business.url,
            } for s in it.stops],
        })

    print(f"\nTrip estimated total: ${total_cost:.0f} over {len(trip)} day(s)")
    print("Costs are estimates; many places have no recorded price. Data snapshot is from Sep 2021.")

    if args.json:
        payload = {"request": {"first_day": req.day, "days": args.days,
                               "interests": list(req.interests), "budget_per_day": req.budget},
                   "days": json_days}
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Wrote {args.json}")
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
