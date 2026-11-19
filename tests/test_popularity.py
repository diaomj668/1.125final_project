import unittest
from planner.planner import Request, build_plan
from planner.checker import check_itinerary
from test_planner import biz, ANCHOR

class PopularityTests(unittest.TestCase):
    def test_more_reviewed_place_beats_nearest(self):
        near = biz('near',42.3602,-71.0589,'Open 24 hours',reviews=10)
        popular = biz('popular',42.37,-71.0589,'Open 24 hours',reviews=5000)
        req = Request('Saturday',('food',),100,max_stops=1)
        plan = build_plan([near,popular],req)
        self.assertEqual(plan.stops[0].business.gmap_id,'popular')
        self.assertEqual(check_itinerary(plan,{b.gmap_id:b for b in [near,popular]}),[])

    def test_closed_low_rated_or_over_budget_popular_places_are_excluded(self):
        records = [biz('closed',42.3602,-71.0589,'Closed',reviews=9000),
                   biz('low-rated',42.3602,-71.0589,'Open 24 hours',rating=3.9,reviews=8000),
                   biz('expensive',42.3602,-71.0589,'Open 24 hours',price='$$$$',reviews=7000),
                   biz('eligible',42.361,-71.0589,'Open 24 hours',price='$',reviews=100)]
        plan = build_plan(records,Request('Saturday',('food',),20,max_stops=1))
        self.assertEqual([s.business.gmap_id for s in plan.stops],['eligible'])

    def test_next_popularity_batch_is_considered_if_first_is_unreachable(self):
        records = [biz(str(i),42.361+i*.001,-71.0589,'Open 24 hours',reviews=1000-i) for i in range(7)]
        class Router:
            shortlist_limit=5
            def minutes(self,origin,dests):
                return [(float('inf') if d[0]<42.366 else 2,'road') for d in dests]
        plan = build_plan(records,Request('Saturday',('food',),100,max_stops=1),router=Router())
        self.assertEqual(plan.stops[0].business.gmap_id,'5')

    def test_all_recommendations_remain_in_input_catalog(self):
        records=[biz('a',42.361,-71.0589,'Open 24 hours',reviews=30),biz('b',42.362,-71.0589,'Open 24 hours',reviews=100)]
        plan=build_plan(records,Request('Saturday',('food',),100,max_stops=4))
        self.assertTrue(set(s.business.gmap_id for s in plan.stops)<=set(b.gmap_id for b in records))
        self.assertEqual(len(plan.stops),len(set(s.business.gmap_id for s in plan.stops)))
