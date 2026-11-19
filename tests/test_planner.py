import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planner.agent import plan_with_checks  # noqa: E402
from planner.checker import check_itinerary  # noqa: E402
from planner.data import Business  # noqa: E402
from planner.hours import earliest_start, is_open, parse_clock, parse_day_hours  # noqa: E402
from planner.planner import Itinerary, Request, Stop, build_plan, estimate_cost  # noqa: E402

ANCHOR = (42.3601, -71.0589)


def biz(gid, lat, lon, hours_text, cats=("Restaurant",), price="$$", rating=4.5, reviews=20):
    return Business(
        gmap_id=gid, name=gid, address=f"{gid}, Boston, MA 02110",
        lat=lat, lon=lon, categories=tuple(cats), rating=rating, n_reviews=reviews,
        price=price, hours={"Saturday": hours_text}, url=f"https://example.test/{gid}",
    )


class HoursTests(unittest.TestCase):
    def test_parse_clock(self):
        self.assertEqual(parse_clock("12AM"), 0)
        self.assertEqual(parse_clock("12PM"), 12 * 60)
        self.assertEqual(parse_clock("5:30AM"), 5 * 60 + 30)
        self.assertIsNone(parse_clock("noon"))

    def test_parse_day_hours(self):
        self.assertEqual(parse_day_hours("9AM–5PM"), [(540, 1020)])
        self.assertEqual(parse_day_hours("Closed"), "closed")
        self.assertEqual(parse_day_hours("Open 24 hours"), "always")
        self.assertIsNone(parse_day_hours(None))
        self.assertIsNone(parse_day_hours("sometimes"))
        # open past midnight
        self.assertEqual(parse_day_hours("6PM–2AM"), [(1080, 1560)])

    def test_is_open_requires_whole_visit(self):
        parsed = parse_day_hours("9AM–5PM")
        self.assertTrue(is_open(parsed, 540, 600))
        self.assertFalse(is_open(parsed, 990, 1050))  # ends after closing
        self.assertFalse(is_open(parsed, 480, 540))   # starts before opening

    def test_earliest_start_waits_for_opening(self):
        parsed = parse_day_hours("9AM–5PM")
        self.assertEqual(earliest_start(parsed, 500, 60), 540)
        self.assertIsNone(earliest_start(parsed, 1000, 60))
        self.assertIsNone(earliest_start("closed", 600, 60))


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.businesses = [
            biz("a", 42.3610, -71.0590, "9AM–6PM"),
            biz("b", 42.3620, -71.0600, "9AM–6PM"),
            biz("c", 42.3630, -71.0610, "Closed"),
            biz("d", 42.3640, -71.0620, "9AM–11AM"),
            biz("e", 42.3650, -71.0630, "9AM–6PM", rating=3.0),
            biz("f", 42.3660, -71.0640, "9AM–6PM", cats=("Museum",), price=None),
        ]
        self.catalog = {b.gmap_id: b for b in self.businesses}
        self.req = Request(day="Saturday", interests=("food", "culture"), budget=200,
                           start_min=10 * 60, end_min=20 * 60, max_stops=4, anchor=ANCHOR)

    def test_excludes_closed_low_rated_and_unknown_hours(self):
        itin = build_plan(self.businesses, self.req)
        ids = {s.business.gmap_id for s in itin.stops}
        self.assertNotIn("c", ids)  # closed that day
        self.assertNotIn("e", ids)  # rating below threshold

    def test_planned_plan_passes_checker(self):
        result = plan_with_checks(self.businesses, self.catalog, self.req)
        self.assertIsNotNone(result.itinerary)
        self.assertEqual(check_itinerary(result.itinerary, self.catalog), [])

    def test_budget_is_respected(self):
        req = Request(day="Saturday", interests=("food", "culture"), budget=30,
                      start_min=10 * 60, end_min=20 * 60, max_stops=4, anchor=ANCHOR)
        itin = build_plan(self.businesses, req)
        self.assertLessEqual(itin.total_cost, 30)

    def test_missing_price_uses_default_estimate(self):
        cost, source = estimate_cost(self.businesses[-1])
        self.assertEqual(cost, 15)
        self.assertIn("no price", source)


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.b = biz("a", 42.3610, -71.0590, "9AM–12PM")
        self.catalog = {"a": self.b}
        self.req = Request(day="Saturday", interests=("food",), budget=100,
                           start_min=10 * 60, end_min=20 * 60, anchor=ANCHOR)

    def stop(self, start, end, interest="food", business=None):
        b = business or self.b
        return Stop(b, interest, start, start, end, 0, 25, "test")

    def test_visit_outside_hours_is_flagged(self):
        itin = Itinerary(self.req, [self.stop(11 * 60 + 30, 12 * 60 + 30)])
        rules = {v.rule for v in check_itinerary(itin, self.catalog)}
        self.assertIn("open_hours", rules)

    def test_unknown_record_is_flagged(self):
        ghost = biz("ghost", 42.36, -71.06, "9AM–5PM")
        itin = Itinerary(self.req, [self.stop(600, 660, business=ghost)])
        rules = {v.rule for v in check_itinerary(itin, {})}
        self.assertIn("record_exists", rules)

    def test_budget_overrun_is_flagged(self):
        req = Request(day="Saturday", interests=("food",), budget=10,
                      start_min=10 * 60, end_min=20 * 60, anchor=ANCHOR)
        itin = Itinerary(req, [self.stop(600, 660)])
        rules = {v.rule for v in check_itinerary(itin, self.catalog)}
        self.assertIn("budget", rules)


if __name__ == "__main__":
    unittest.main()
