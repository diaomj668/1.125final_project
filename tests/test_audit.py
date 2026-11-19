import unittest
from dataclasses import replace
from planner.hours import parse_clock, parse_day_hours
from planner.planner import Request, Stop, Itinerary, build_plan
from planner.optimizer import improve_route, metrics, schedule
from planner.checker import check_itinerary
from planner.server import build_request, HttpError
from test_planner import biz

class AuditTests(unittest.TestCase):
    def test_invalid_clock_and_abbreviated_noon(self):
        self.assertIsNone(parse_clock('13PM'))
        self.assertIsNone(parse_clock('0AM'))
        self.assertEqual(parse_day_hours('12–5PM'),[(720,1020)])
        self.assertEqual(parse_day_hours('1–5PM'),[(780,1020)])
        self.assertIsNone(parse_day_hours('9–5PM'))

    def test_reorder_reduces_travel_and_keeps_every_stop(self):
        records=[biz(str(i),42.36+x,-71.0589,'Open 24 hours',cats=('Museum',)) for i,x in enumerate([.01,.03,.02])]
        req=Request('Saturday',('culture',),100,start_min=480,end_min=1200,max_stops=3)
        old=[Stop(b,'culture',480,480,570,0,25,'estimate') for b in records]
        initial=schedule(old,req,None)
        improved=improve_route(initial)
        self.assertLess(metrics(improved,None)[0],metrics(initial,None)[0])
        self.assertEqual(set(s.business.gmap_id for s in initial.stops),set(s.business.gmap_id for s in improved.stops))
        self.assertEqual(check_itinerary(improved,{b.gmap_id:b for b in records}),[])

    def test_meals_and_missing_meal_validation(self):
        records=[biz(str(i),42.3601,-71.0589,'Open 24 hours',cats=('Restaurant','Breakfast restaurant')) for i in range(4)]
        req=Request('Saturday',('food',),200,start_min=480,end_min=1260,max_stops=6)
        plan=build_plan(records,req)
        self.assertEqual([s.meal for s in plan.stops],['Breakfast','Lunch','Dinner'])
        self.assertEqual([s.meal for s in improve_route(plan).stops],['Breakfast','Lunch','Dinner'])
        bad=Itinerary(req,[replace(plan.stops[0],meal='')])
        self.assertIn('meal_time',[v.rule for v in check_itinerary(bad,{b.gmap_id:b for b in records})])

    def test_invalid_input(self):
        class Geocoder: pass
        for body in [{'budget':float('nan')},{'budget':-1},{'start_time':'25:00'},{'end_time':'12:99'}]:
            with self.assertRaises(HttpError): build_request(body,Geocoder())
