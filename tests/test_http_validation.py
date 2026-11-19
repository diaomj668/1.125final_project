import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from planner.server import make_handler, build_request, HttpError

class ValidationTests(unittest.TestCase):
    def test_bad_types_are_client_errors(self):
        class Geocoder: pass
        for body in [[], {'days':'abc'}, {'days':1.5}, {'max_stops':True}, {'budget':None}, {'interests':'food'}, {'start_place':42}]:
            with self.subTest(body=body), self.assertRaises(HttpError) as caught:
                build_request(body,Geocoder())
            self.assertEqual(caught.exception.status,400)

    def test_duplicate_interests_do_not_change_interest_limits(self):
        req,*_=build_request({'interests':['food','food','culture']},object())
        self.assertEqual(req.interests,('food','culture'))

    def test_http_rejects_nonobject_large_and_invalid_chat_requests(self):
        class App:
            def plan(self,body): raise AssertionError('Invalid request must never reach planner')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(App()))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}/api/chat'
            for payload,code in [(b'[]',400),(b'{bad',400),(json.dumps({'message':123}).encode(),400),(json.dumps({'message':'x'*4001}).encode(),400),(b' '*65537,413)]:
                with self.subTest(code=code), self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(urllib.request.Request(url,data=payload,headers={'Content-Type':'application/json'}),timeout=5)
                self.assertEqual(caught.exception.code,code)
                self.assertIn('error',json.loads(caught.exception.read()))
                caught.exception.close()
        finally:
            server.shutdown();server.server_close();thread.join()
