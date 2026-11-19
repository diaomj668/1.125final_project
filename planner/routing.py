"""Driving times along the road network, from the public OSRM server.

OSRM routes over OpenStreetMap roads. It gives typical driving times, not live
traffic. If the server cannot be reached, the router falls back to the
straight-line estimate for those pairs and labels them as such.

Results are cached in a JSON file, so repeated runs do not call the server again.
The public demo server is for light use only; do not run large batches against it.
"""
import json
import math
import urllib.error
import urllib.request
from pathlib import Path

from .geo import travel_minutes, haversine_km

OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"
TIMEOUT_SECONDS = 20


class Router:
    def __init__(self, cache_path=None, use_network=True):
        self.cache_path = Path(cache_path) if cache_path else None
        self.use_network = use_network
        self.cache = {}
        self.offline = False
        if self.cache_path and self.cache_path.exists():
            self.cache = json.loads(self.cache_path.read_text(encoding="utf-8"))

    @staticmethod
    def _key(origin, dest):
        return f"{origin[0]:.5f},{origin[1]:.5f}>{dest[0]:.5f},{dest[1]:.5f}"

    def _fetch(self, origin, dests):
        coords = [origin] + dests
        path = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
        url = f"{OSRM_TABLE_URL}{path}?sources=0&annotations=duration"
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") != "Ok":
            raise ValueError(data.get("code"))
        return data["durations"][0][1:]

    def minutes(self, origin, dests):
        """Driving minutes (rounded up) from origin to each destination.
        Returns a list of (minutes, source); source is 'road' or 'straight-line'."""
        missing = [d for d in dests if self._key(origin, d) not in self.cache]
        if missing and self.use_network and not self.offline:
            try:
                secs = self._fetch(origin, missing)
                for d, s in zip(missing, secs):
                    if s is not None:
                        self.cache[self._key(origin, d)] = s / 60.0
                self._save()
            except (urllib.error.URLError, OSError, ValueError, KeyError, json.JSONDecodeError):
                self.offline = True

        out = []
        for d in dests:
            m = self.cache.get(self._key(origin, d))
            if m is None:
                out.append((math.ceil(travel_minutes(origin[0], origin[1], d[0], d[1])), "straight-line"))
            else:
                out.append((math.ceil(m), "road"))
        return out

    def _save(self):
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache), encoding="utf-8")


class RoutingError(Exception):
    """A routing provider could not supply usable results."""


class TripRouter:
    """One router per planning request. Google results are never saved to disk."""
    def __init__(self, mode="walking", google_key=None, parking_min=5, trip_date=None):
        from datetime import date
        self.mode = mode
        self.google_key = google_key
        self.parking_min = parking_min if mode == "driving" else 0
        self.trip_date = trip_date or date.today().isoformat()
        self.road = Router()
        self.offline = False
        self.used_google = False
        self.google_failed = False
        self.legs = {}
        self.notes = set()
        self.memo = {}
        self.shortlist_limit = 5 if google_key else 25
        if mode == "transit" and not google_key:
            raise RoutingError("Transit needs a Google Routes API key on the server. Choose walking or driving for now.")

    def _google(self, origin, dests, depart_min, trip_date):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        def waypoint(ll):
            return {"waypoint": {"location": {"latLng": {"latitude": ll[0], "longitude": ll[1]}}}}
        body = {"origins": [waypoint(origin)], "destinations": [waypoint(d) for d in dests],
                "travelMode": {"walking": "WALK", "driving": "DRIVE", "transit": "TRANSIT"}[self.mode]}
        if self.mode == "driving":
            body["routingPreference"] = "TRAFFIC_UNAWARE"
        if self.mode == "transit":
            departure = datetime.fromisoformat(trip_date).replace(tzinfo=ZoneInfo("America/New_York")) + timedelta(minutes=depart_min)
            body["departureTime"] = departure.isoformat()
        req = urllib.request.Request("https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
            "X-Goog-Api-Key": self.google_key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,status,condition,duration"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            elements = json.load(resp)
        if not isinstance(elements, list):
            raise RoutingError("Google Routes returned an invalid response.")
        times = [None] * len(dests)
        for item in elements:
            if item.get("status", {}).get("code", 0):
                raise RoutingError("Google Routes could not calculate this route matrix.")
            idx = item.get("destinationIndex", 0)
            if not 0 <= idx < len(dests):
                raise RoutingError("Invalid route index.")
            if item.get("condition") == "ROUTE_NOT_FOUND":
                times[idx] = (math.inf, "unreachable")
            elif item.get("condition") == "ROUTE_EXISTS" and "duration" in item:
                minutes = math.ceil(float(item["duration"].removesuffix("s")) / 60)
                times[idx] = (minutes + self.parking_min, "google")
        if any(t is None for t in times):
            raise RoutingError("Google Routes returned incomplete travel times.")
        self.used_google = True
        return times

    def minutes_at(self, origin, dests, depart_min=0, trip_date=None):
        trip_date = trip_date or self.trip_date
        key = (tuple(origin), tuple(map(tuple, dests)), depart_min, trip_date)
        if key in self.memo:
            return self.memo[key]
        pair_keys = [(tuple(origin), tuple(d), depart_min, trip_date) for d in dests]
        if all(k in self.legs for k in pair_keys):
            return [self.legs[k] for k in pair_keys]
        if self.google_key and not self.google_failed:
            try:
                result = self._google(origin, dests, depart_min, trip_date)
                self.memo[key] = result
                self.legs.update(zip(pair_keys, result))
                return result
            except (urllib.error.URLError, OSError, ValueError, KeyError, RoutingError) as exc:
                if self.mode == "transit":
                    raise RoutingError("Google transit routing failed. Check the server key, Routes API access and trip date; no driving estimate was substituted.") from exc
                self.google_failed = True
                self.notes.add("Google Routes unavailable; fallback times are labelled below.")
        if self.mode == "walking":
            self.notes.add("Walking estimate: straight-line distance × 1.3 at 4.5 km/h; paths, crossings and accessibility are not verified.")
            result = [(math.ceil(haversine_km(origin[0], origin[1], d[0], d[1]) * 1.3 / 4.5 * 60), "walking-estimate") for d in dests]
        else:
            result = [(m + self.parking_min, source) for m, source in self.road.minutes(origin, dests)]
            self.offline = self.road.offline
            self.notes.add("Driving times exclude live traffic; parking/walking buffer is added to every leg.")
        self.memo[key] = result
        self.legs.update(zip(pair_keys, result))
        return result

    def minutes(self, origin, dests):
        return self.minutes_at(origin, dests)
