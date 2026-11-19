"""Run 20 fixed sample requests and report the checker results.

Targets from the proposal:
  - 0 time clashes in final plans (code check)
  - 0 record/hour violations; dollar costs remain explicitly labelled assumptions

Usage:
    python scripts/evaluate.py --data data/raw
Writes evaluation/results.md.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from planner.agent import plan_with_checks  # noqa: E402
from planner.data import load_businesses  # noqa: E402
from planner.planner import DAYS, Request  # noqa: E402

COMBOS = [
    ("food",), ("culture",), ("outdoors",), ("shopping",), ("nightlife",),
    ("food", "culture"), ("food", "outdoors"), ("culture", "outdoors"),
    ("food", "shopping"), ("food", "nightlife"),
]
BUDGETS = [40, 60, 80, 100]
HOURS_RULES = {"open_hours", "hours_unknown", "traceability", "record_exists"}


def build_requests():
    reqs = []
    for i in range(20):
        reqs.append(Request(
            day=DAYS[i % 7],
            interests=COMBOS[i % len(COMBOS)],
            budget=BUDGETS[i % len(BUDGETS)],
            start_min=10 * 60, end_min=20 * 60, max_stops=4,
        ))
    return reqs


def clashes(stops):
    ordered = sorted(stops, key=lambda s: s.start_min)
    return sum(1 for a, b in zip(ordered, ordered[1:]) if b.start_min < a.end_min)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/raw")
    p.add_argument("--out", default=str(ROOT / "evaluation" / "results.md"))
    args = p.parse_args()

    businesses, stats = load_businesses(args.data)
    catalog = {b.gmap_id: b for b in businesses}

    rows = []
    for n, req in enumerate(build_requests(), 1):
        result = plan_with_checks(businesses, catalog, req)
        final_violations = result.attempts[-1].get("violations", []) if result.attempts else []
        if result.itinerary is None:
            rows.append({"n": n, "req": req, "planned": False, "stops": 0,
                         "attempts": len(result.attempts), "clashes": 0,
                         "made_up": 0, "budget_ok": True, "cost": 0.0})
            continue
        it = result.itinerary
        made_up = sum(1 for v in final_violations if v.rule in HOURS_RULES)
        rows.append({"n": n, "req": req, "planned": True, "stops": len(it.stops),
                     "attempts": len(result.attempts), "clashes": clashes(it.stops),
                     "made_up": made_up,
                     "budget_ok": it.total_cost <= req.budget, "cost": it.total_cost})

    planned = sum(r["planned"] for r in rows)
    rebuilt = sum(1 for r in rows if r["attempts"] > 1)
    total_clashes = sum(r["clashes"] for r in rows)
    total_made_up = sum(r["made_up"] for r in rows)
    budget_fail = sum(1 for r in rows if r["planned"] and not r["budget_ok"])

    lines = [
        "# Evaluation: 20 sample requests (planner with checker)",
        "",
        f"Data: {stats['kept']} businesses after removing {stats['permanently_closed']} "
        f"permanently closed, {stats['out_of_state']} out-of-state and "
        f"{stats['bad_coordinates']} with bad coordinates.",
        "",
        f"- Requests with a checked plan: {planned} / {len(rows)}",
        f"- Plans that needed a rebuild: {rebuilt}",
        f"- Time clashes in final plans (target 0): {total_clashes}",
        f"- Hours/record violations in final plans (target 0): {total_made_up}",
        f"- Plans over budget (target 0): {budget_fail}",
        "",
        "| # | Day | Interests | Budget | Plan? | Stops | Attempts | Clashes | Hours issues | Est. cost |",
        "|---|-----|-----------|--------|-------|-------|----------|---------|--------------|-----------|",
    ]
    for r in rows:
        q = r["req"]
        lines.append(
            f"| {r['n']} | {q.day} | {', '.join(q.interests)} | ${q.budget:.0f} | "
            f"{'yes' if r['planned'] else 'no'} | {r['stops']} | {r['attempts']} | "
            f"{r['clashes']} | {r['made_up']} | ${r['cost']:.0f} |"
        )
    lines += [
        "",
        "Method: offline planner/checker evaluation using straight-line driving estimates; no live Google routing, geocoding or LLM calls.",
        "Dollar costs are explicit price-tier assumptions, not factual menu or admission prices. These checks do not establish current operating hours or optimal routes.",
        "Not yet done: a plain-chatbot baseline on the same 20 requests.",
        "",
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:9]))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
