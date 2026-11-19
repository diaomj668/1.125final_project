import unittest
from dataclasses import replace
from planner.planner import Request, build_plan
from planner.checker import check_itinerary
from planner.server import build_request
from test_planner import biz

class CityScopeTests(unittest.TestCase):
    def test_more_popular_outside_city_is_never_recommended(self):
        local=replace(biz('local',42.52,-70.9,'Open 24 hours',reviews=100),address='Shop, 1 Essex St, Salem, MA 01970')
        outside=replace(biz('outside',42.5,-70.9,'Open 24 hours',reviews=9000),address='Shop, 2 Main St, Saugus, MA 01906')
        req=Request('Sunday',('food',),100,anchor=(42.52,-70.9),scope_city='Salem',max_stops=1)
        records=[replace(b,hours={'Sunday':'Open 24 hours'}) for b in [local,outside]]
        plan=build_plan(records,req)
        self.assertEqual([s.business.gmap_id for s in plan.stops],['local'])
        self.assertEqual(check_itinerary(plan,{b.gmap_id:b for b in records}),[])

    def test_walking_leg_limit_prevents_hours_long_detour(self):
        near=biz('near',42.361,-71.059,'Open 24 hours',reviews=10)
        far=biz('far',42.37,-71.059,'Open 24 hours',reviews=9000)
        class Router:
            def minutes(self,origin,dests): return [(210 if d==(far.lat,far.lon) else 5,'road') for d in dests]
        plan=build_plan([near,far],Request('Saturday',('food',),100,max_stops=1,max_leg_min=45),router=Router())
        self.assertEqual(plan.stops[0].business.gmap_id,'near')

    def test_empty_local_candidate_pool_does_not_expand_to_other_city(self):
        outside=replace(biz('outside',42.361,-71.059,'Open 24 hours',reviews=9000),address='Shop, 2 Main St, Saugus, MA 01906')
        plan=build_plan([outside],Request('Saturday',('food',),100,scope_city='Salem'))
        self.assertEqual(plan.stops,[])

    def test_city_is_inferred_but_cross_city_endpoints_still_work(self):
        class Geocoder:
            def lookup(self,text): return {'lat':42.52,'lon':-70.9,'city':'Salem' if text=='Salem' else 'Boston','label':text}
        req,*_=build_request({'start_place':'Salem','travel_mode':'walking'},Geocoder())
        self.assertEqual(req.scope_city,'Salem')
        self.assertEqual(req.max_leg_min,45)
        req,*_=build_request({'start_place':'Salem','end_place':'Boston'},Geocoder())
        self.assertEqual(req.scope_city,'')
        req,*_=build_request({'start_place':'Salem','end_place':'Boston','destination_city':'Salem'},Geocoder())
        self.assertEqual(req.scope_city,'Salem')
