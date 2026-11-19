import json
import math
import unittest
from unittest.mock import patch
from planner.routing import TripRouter, RoutingError
from planner.planner import Request, build_plan
from planner.checker import check_itinerary
from test_planner import biz, ANCHOR

class TravelModeTests(unittest.TestCase):
    def test_walking_uses_walking_speed_and_label(self):
        router = TripRouter('walking')
        with patch.object(router.road, 'minutes', side_effect=AssertionError('Must not use driving')):
            duration, source = router.minutes(ANCHOR, [(42.37, -71.0589)])[0]
        self.assertGreater(duration, 15)
        self.assertEqual(source, 'walking-estimate')

    def test_driving_buffer_is_part_of_planning_time(self):
        router = TripRouter('driving', parking_min=5)
        with patch.object(router.road, 'minutes', return_value=[(2, 'road')]):
            self.assertEqual(router.minutes(ANCHOR, [(42.37, -71.0589)]), [(7, 'road')])

    def test_transit_without_key_fails_instead_of_using_driving(self):
        with self.assertRaises(RoutingError):
            TripRouter('transit')

    def test_return_leg_uses_forward_direction(self):
        end = (42.38, -71.04)
        b = biz('a',42.361,-71.059,'Open 24 hours')
        class AsymmetricRouter:
            def minutes(self, origin, dests):
                return [(100 if origin == (b.lat,b.lon) and d == end else 1,'road') for d in dests]
        req = Request('Saturday',('food',),100,start_min=600,end_min=680,max_stops=1,end_point=end)
        self.assertEqual(build_plan([b],req,router=AsymmetricRouter()).stops, [])

    def test_google_matrix_order_no_route_and_subset_reuse(self):
        router=TripRouter('walking',google_key='test-only')
        class Response:
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def read(self):
                return json.dumps([
                    {'destinationIndex':1,'condition':'ROUTE_NOT_FOUND','status':{}},
                    {'destinationIndex':0,'condition':'ROUTE_EXISTS','duration':'125s','status':{}}
                ]).encode()
        dests=[(42.37,-71.06),(42.38,-71.07)]
        with patch('urllib.request.urlopen', return_value=Response()) as call:
            values=router.minutes_at(ANCHOR,dests,600,'2026-11-21')
            self.assertEqual(values[0],(3,'google'))
            self.assertTrue(math.isinf(values[1][0]))
            self.assertEqual(router.minutes_at(ANCHOR,dests[:1],600,'2026-11-21'),values[:1])
            self.assertEqual(call.call_count,1)

    def test_transit_departure_changes_query_and_uses_eastern_time(self):
        router=TripRouter('transit',google_key='test-only')
        class Response:
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def read(self): return b'[{"condition":"ROUTE_EXISTS","duration":"600s"}]'
        with patch('urllib.request.urlopen',return_value=Response()) as call:
            router.minutes_at(ANCHOR,[(42.37,-71.06)],600,'2026-11-21')
            first=json.loads(call.call_args.args[0].data)
            router.minutes_at(ANCHOR,[(42.37,-71.06)],660,'2026-11-21')
            second=json.loads(call.call_args.args[0].data)
        self.assertEqual(first['departureTime'],'2026-11-21T10:00:00-05:00')
        self.assertNotEqual(first['departureTime'],second['departureTime'])
        self.assertNotIn('routingPreference',first)

    def test_transit_api_failure_is_explicit(self):
        router=TripRouter('transit',google_key='test-only')
        with patch.object(router,'_google',side_effect=OSError('offline')):
            with self.assertRaises(RoutingError): router.minutes(ANCHOR,[(42.37,-71.06)])

    def test_new_walking_times_schedule_and_checker_agree(self):
        b=biz('a',42.37,-71.0589,'Open 24 hours')
        router=TripRouter('walking')
        req=Request('Saturday',('food',),100,travel_mode='walking',trip_date='2026-11-21')
        plan=build_plan([b],req,router=router)
        self.assertGreater(plan.stops[0].arrival_min,req.start_min+15)
        self.assertEqual(check_itinerary(plan,{'a':b},router),[])


class EndLegResponseTests(unittest.TestCase):
    def test_fixed_end_plan_serializes_last_leg(self):
        from planner.server import serialize_plan
        from planner.agent import PlanResult
        b = biz('a', 42.361, -71.059, 'Open 24 hours')
        end = (42.37, -71.06)
        router = TripRouter('walking', trip_date='2026-11-21')
        req = Request('Saturday', ('food',), 100, max_stops=1, end_point=end,
                      travel_mode='walking', trip_date='2026-11-21')
        itinerary = build_plan([b], req, router=router)
        self.assertEqual(len(itinerary.stops), 1)
        result = serialize_plan([('Saturday', PlanResult(itinerary, []))], req,
            {'lat': ANCHOR[0], 'lon': ANCHOR[1], 'label': 'Start'},
            {'lat': end[0], 'lon': end[1], 'label': 'End'}, router, 1)
        leg = result['days'][0]['end_leg']
        self.assertGreater(leg['travel_min'], 0)
        self.assertEqual(leg['travel_source'], 'walking-estimate')
        self.assertIn(':', leg['arrival'])
