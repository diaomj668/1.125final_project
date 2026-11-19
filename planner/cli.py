"""Command-line entry point.

Example:
    python -m planner --data data/raw --day Saturday --interests food,outdoors --budget 80
"""
import argparse
import json
import sys

from .agent import plan_with_checks
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
    p = argparse.ArgumentParser(description="One-day Massachusetts trip planner with checks.")
    p.add_argument("--data", default="data/raw", help="folder with meta-Massachusetts.json.gz")
    p.add_argument("--day", default="Saturday", choices=DAYS)
    p.add_argument("--interests", default="food,culture", help="comma list: " + ", ".join(INTEREST_NAMES))
    p.add_argument("--budget", type=float, default=80.0, help="estimated total USD per person")
    p.add_argument("--start", default="10:00", help="HH:MM, 24h")
    p.add_argument("--end", default="20:00", help="HH:MM, 24h")
    p.add_argument("--max-stops", type=int, default=4)
    p.add_argument("--anchor", default=f"{BOSTON_ANCHOR[0]},{BOSTON_ANCHOR[1]}", help="lat,lon of the start")
    p.add_argument("--radius-km", type=float, default=20.0)
    p.add_argument("--json", metavar="PATH", help="also write the plan as JSON")
    args = p.parse_args(argv)

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
    result = plan_with_checks(businesses, catalog, req)

    print(f"\nPlan for {req.day}, interests: {', '.join(interests)}, budget ${req.budget:.0f}")
    print("Checker log:")
    for a in result.attempts:
        if "note" in a:
            print(f"  attempt {a['attempt']}: {a['note']}")
            continue
        if a["violations"]:
            print(f"  attempt {a['attempt']}: {len(a['violations'])} violation(s)")
            for v in a["violations"]:
                print(f"      - [{v.rule}] {v.message}")
        else:
            print(f"  attempt {a['attempt']}: {a['stops']} stop(s), all checks passed")

    if result.itinerary is None:
        print("\nNo checked plan found. Try a bigger radius, more interests, or a larger budget.")
        return 1

    it = result.itinerary
    print()
    for n, s in enumerate(it.stops, 1):
        b = s.business
        print(f"{n}. {fmt(s.start_min)}–{fmt(s.end_min)}  {b.name}  [{s.interest}]")
        print(f"     {b.address}")
        print(f"     travel {s.travel_min} min · est. ${s.cost:.0f} ({s.cost_source})"
              f" · rating {b.rating} ({b.n_reviews} reviews)")
        print(f"     hours {req.day}: {b.hours.get(req.day)}")
        print(f"     record: {b.url}")
    print(f"\nEstimated total: ${it.total_cost:.0f} of ${req.budget:.0f} budget")
    print("Costs are estimates; many places have no recorded price. Data snapshot is from Sep 2021.")

    if args.json:
        payload = {
            "request": {"day": req.day, "interests": list(req.interests), "budget": req.budget},
            "stops": [{
                "name": s.business.name, "gmap_id": s.business.gmap_id, "interest": s.interest,
                "start": fmt(s.start_min), "end": fmt(s.end_min), "travel_min": s.travel_min,
                "cost_estimate": s.cost, "hours": s.business.hours.get(req.day), "url": s.business.url,
            } for s in it.stops],
            "attempts": len(result.attempts),
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
