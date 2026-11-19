"""Local web server: the planning page, a chat box that uses Claude, and the planning API.

Run:
    export ANTHROPIC_API_KEY=...        # your own key; only needed for the chat box
    python -m planner.server --data data/raw
    then open http://127.0.0.1:8000

The API key is read from the environment on this machine. It is never sent to the page
and never written to any file.

Endpoints:
    GET  /                 the planning page (web/index.html)
    POST /api/chat         {"message": "..."} -> {"reply": "...", "params": {...}}
    POST /api/plan         trip parameters -> checked plan per day, with map coordinates
"""
import argparse
import json
import os
import threading
import time
from collections import defaultdict, deque
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .agent import plan_trip
from .data import load_businesses, address_city
from .interests import INTEREST_NAMES
from .planner import BOSTON_ANCHOR, DAYS, Request
from .routing import Router, TripRouter, RoutingError

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
ANTHROPIC_BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Generic client name, as required for OpenStreetMap's Nominatim service.
GEOCODER_USER_AGENT = "massachusetts-trip-planner-local/0.1"
MA_VIEWBOX = "-73.6,41.2,-69.8,42.9"  # lon/lat bounds of Massachusetts

TRIP_TOOL = {
    "name": "set_trip_request",
    "description": "Set the parameters of a Massachusetts trip plan. Call this exactly once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "destination_city": {"type": ["string", "null"], "description": "City the trip is IN, e.g. Salem for Sunday in Salem. Use null for trips spanning cities or only specifying a start landmark."},
            "travel_mode": {"type": "string", "enum": ["walking", "driving", "transit"]},
            "trip_date": {"type": ["string", "null"], "description": "Explicit departure date YYYY-MM-DD when user supplies a date; otherwise null and use first_day."},
            "first_day": {"type": "string", "enum": list(DAYS), "description": "first day of the trip"},
            "days": {"type": "integer", "minimum": 1, "maximum": 7, "description": "number of consecutive days"},
            "interests": {"type": "array", "items": {"type": "string", "enum": list(INTEREST_NAMES)}},
            "budget_per_day": {"type": "number", "description": "estimated spend per day, USD per person"},
            "start_time": {"type": "string", "description": "HH:MM, 24-hour"},
            "end_time": {"type": "string", "description": "HH:MM, 24-hour"},
            "max_stops_per_day": {"type": "integer", "minimum": 1, "maximum": 12},
            "start_place": {"type": ["string", "null"], "description": "where the day starts, e.g. 'Harvard Square'; null for Boston Common"},
            "end_place": {"type": ["string", "null"], "description": "where the day must end; null if no fixed end"},
            "notes": {"type": "string", "description": "requests the planner cannot act on, such as 'no museums'"},
        },
        "required": ["first_day", "days", "interests", "budget_per_day", "start_time", "end_time"],
    },
}

SYSTEM_PROMPT = (
    "You help plan one-day or multi-day trips in Massachusetts. Read the user's message and call "
    "set_trip_request with the parameters. Fill in defaults for anything not stated: first day Saturday, "
    "1 day, interests food and culture, budget 80 per day, 10:00 to 20:00, 4 stops per day, start and end "
    "not fixed. If the user says in a city (such as Sunday in Salem), set destination_city to that city and start_place to that city unless another start is specified. All recommended stops must remain in that city. Default travel_mode walking; use driving or transit only if requested. Use Massachusetts place names for start_place and end_place. Put requests the planner cannot "
    "handle (for example booking or live availability) in notes. Always reply in English, regardless of the input language. Write notes in English. Then reply briefly in English, "
    "saying what you assumed."
)


# ---------- Limits (protect your API budget when the server is public) ----------

CHAT_PER_IP_PER_HOUR = int(os.environ.get("CHAT_PER_IP_PER_HOUR", "20"))
PLAN_PER_IP_PER_HOUR = int(os.environ.get("PLAN_PER_IP_PER_HOUR", "60"))
CHAT_DAILY_CAP = int(os.environ.get("CHAT_DAILY_CAP", "300"))  # all visitors together, Claude calls per UTC day


class Limiter:
    """Sliding-window limits per client, plus a daily cap on Claude calls for everyone."""

    def __init__(self):
        self.hits = defaultdict(deque)
        self.daily = {"day": None, "count": 0}
        self.lock = threading.Lock()

    def allow(self, key, limit, window_seconds=3600):
        now = time.time()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def take_daily(self):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        with self.lock:
            if self.daily["day"] != today:
                self.daily = {"day": today, "count": 0}
            if self.daily["count"] >= CHAT_DAILY_CAP:
                return False
            self.daily["count"] += 1
            return True


LIMITER = Limiter()


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


# ---------- Claude ----------

def call_claude_for_params(message):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise HttpError(503, "ANTHROPIC_API_KEY is not set on this computer. Set it, then restart the server.")
    body = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT + " Current date in Massachusetts: " + __import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("America/New_York")).date().isoformat(),
        "tools": [TRIP_TOOL],
        "tool_choice": {"type": "auto"},
        "messages": [{"role": "user", "content": message}],
    }
    req = urllib.request.Request(
        f"{ANTHROPIC_BASE}/v1/messages", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HttpError(502, f"Claude API returned HTTP {e.code}. Check the API key and model name.")
    except (urllib.error.URLError, OSError) as e:
        raise HttpError(502, f"Could not reach the Claude API: {e}")

    params, reply_parts = None, []
    for block in data.get("content", []):
        if block.get("type") == "tool_use" and block.get("name") == "set_trip_request":
            params = block.get("input")
        elif block.get("type") == "text":
            reply_parts.append(block.get("text", ""))
    if params is None:
        raise HttpError(502, "Claude did not return trip parameters. Try rewording the request.")
    return {"reply": "\n".join(p for p in reply_parts if p).strip(), "params": params}


# ---------- Geocoding ----------

class Geocoder:
    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()
        self.last_call = 0.0

    def lookup(self, text):
        """Return {'lat', 'lon', 'label'} for a Massachusetts place name, or raise HttpError."""
        key = text.strip().lower()
        if key in self.cache:
            return self.cache[key]
        with self.lock:  # Nominatim asks for at most one request per second
            wait = 1.0 - (time.time() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.time()
            qs = urllib.parse.urlencode({"q": text, "format": "json", "limit": 1,
                                         "countrycodes": "us", "addressdetails": 1, "viewbox": MA_VIEWBOX, "bounded": 1})
            req = urllib.request.Request(f"{NOMINATIM_URL}?{qs}", headers={"User-Agent": GEOCODER_USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    hits = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, OSError, ValueError) as e:
                raise HttpError(502, f"Could not look up '{text}': {e}")
        if not hits:
            raise HttpError(400, f"Could not find '{text}' in Massachusetts. Try a more specific name.")
        address = hits[0].get("address") or {}
        city = address.get("city") or address.get("town") or address.get("municipality") or ""
        place = {"city": city, "lat": float(hits[0]["lat"]), "lon": float(hits[0]["lon"]), "label": hits[0].get("display_name", text)}
        self.cache[key] = place
        return place


# ---------- Planning ----------

def parse_clock(text):
    try:
        h, m = str(text).split(":")
        h, m = int(h), int(m)
        if not 0 <= h <= 23 or not 0 <= m <= 59: raise ValueError()
        return h * 60 + m
    except (ValueError, TypeError):
        raise HttpError(400, "Use a valid time in HH:MM format.")


def build_request(body, geocoder, known_cities=()):
    from datetime import date, datetime, timedelta
    from zoneinfo import ZoneInfo
    day = body.get("day") or body.get("first_day") or "Saturday"
    if day not in DAYS:
        raise HttpError(400, f"unknown day: {day}")
    mode = body.get("travel_mode", "walking")
    if mode not in ("walking", "driving", "transit"):
        raise HttpError(400, "Choose walking, driving or transit.")
    today = datetime.now(ZoneInfo("America/New_York")).date()
    try:
        trip_date = date.fromisoformat(body["trip_date"]) if body.get("trip_date") else today + timedelta(days=(DAYS.index(day) - today.weekday()) % 7)
    except ValueError:
        raise HttpError(400, "Invalid trip date.")
    if mode == "transit" and trip_date < today:
        raise HttpError(400, "Choose a current or future date for transit.")
    day = DAYS[trip_date.weekday()]
    n_days = int(body.get("days", 1))
    if not 1 <= n_days <= 7:
        raise HttpError(400, "days must be between 1 and 7")
    interests = tuple(i for i in body.get("interests", ["food", "culture"]) if i in INTEREST_NAMES)
    if not interests:
        raise HttpError(400, "pick at least one interest")
    start_text = (body.get("start_place") or "").strip()
    end_text = (body.get("end_place") or "").strip()
    start = geocoder.lookup(start_text) if start_text else {
        "lat": BOSTON_ANCHOR[0], "lon": BOSTON_ANCHOR[1], "label": "Boston Common"}
    end = geocoder.lookup(end_text) if end_text else None
    scope_city = (body.get("destination_city") or "").strip()
    if scope_city:
        scope_city = geocoder.lookup(scope_city).get("city") or scope_city
    elif start_text and not end_text:
        # A city-only day trip stays in its starting municipality. Cross-city trips with an end remain possible.
        scope_city = start.get("city", "")
        if not scope_city:
            scope_city = next((city for city in known_cities if start_text.casefold() in (city.casefold(), city.casefold() + ", ma", city.casefold() + ", massachusetts")), "")
    req = Request(
        day=day, travel_mode=mode, trip_date=trip_date.isoformat(), scope_city=scope_city, max_leg_min=45 if mode == "walking" else None, interests=interests, budget=float(body.get("budget_per_day", body.get("budget", 80))),
        start_min=parse_clock(body.get("start_time", "10:00")), end_min=parse_clock(body.get("end_time", "20:00")),
        max_stops=int(body.get("max_stops_per_day", body.get("max_stops", 4))),
        anchor=(start["lat"], start["lon"]), radius_km=20.0,
        end_point=(end["lat"], end["lon"]) if end else None)
    if not __import__("math").isfinite(req.budget) or req.budget < 0:
        raise HttpError(400, "Budget must be a finite nonnegative number.")
    if not 1 <= req.max_stops <= 12:
        raise HttpError(400, "Max stops per day must be between 1 and 12.")
    if req.end_min <= req.start_min:
        raise HttpError(400, "the end time must be after the start time")
    return req, n_days, start, end


def fmt(minutes):
    return f"{(int(minutes) // 60) % 24:02d}:{int(minutes) % 60:02d}"


def serialize_plan(trip, req, start, end, router, day_count):
    days = []
    total = 0.0
    for day, result in trip:
        attempts = []
        for a in result.attempts:
            if "note" in a:
                attempts.append({"n": a["attempt"], "stops": 0, "note": a["note"], "violations": []})
            else:
                attempts.append({"n": a["attempt"], "stops": a["stops"],
                                 "violations": [{"rule": v.rule, "message": v.message} for v in a["violations"]]})
        stops = []
        if result.itinerary is not None:
            for s in result.itinerary.stops:
                b = s.business
                total += s.cost
                stops.append({
                    "dataset_id": b.gmap_id,
                    "recommendation_reason": f"{b.n_reviews:,} dataset reviews · {b.rating:.1f} stars; selected for popularity, quality, interests and distance",
                    "name": b.name, "address": b.address, "lat": b.lat, "lon": b.lon,
                    "interest": s.interest, "meal": s.meal, "start": fmt(s.start_min), "end": fmt(s.end_min),
                    "start_min": s.start_min, "end_min": s.end_min,
                    "travel_min": s.travel_min, "travel_source": s.travel_source,
                    "cost": s.cost, "cost_source": s.cost_source,
                    "rating": b.rating, "reviews": b.n_reviews, "hours": b.hours.get(day),
                    "url": b.url,
                })
        end_leg = None
        if end and result.itinerary and result.itinerary.stops:
            last = result.itinerary.stops[-1]
            minutes, source = router.minutes_at((last.business.lat, last.business.lon), [req.end_point], last.end_min, result.itinerary.request.trip_date)[0]
            end_leg = {"travel_min": minutes, "travel_source": source, "arrival": fmt(last.end_min + minutes)}
        travel_total = sum(s["travel_min"] for s in stops) + (end_leg["travel_min"] if end_leg else 0)
        waiting_total = sum(s.start_min - s.arrival_min for s in result.itinerary.stops) if result.itinerary else 0
        days.append({"travel_total_min": travel_total, "waiting_total_min": waiting_total, "end_leg": end_leg, "trip_date": result.itinerary.request.trip_date if result.itinerary else None, "day": day, "planned": result.itinerary is not None, "stops": stops, "attempts": attempts})
    return {
        "start": {"lat": start["lat"], "lon": start["lon"], "label": start["label"]},
        "end": {"lat": end["lat"], "lon": end["lon"], "label": end["label"]} if end else None,
        "days": days, "total_cost": total, "budget_per_day": req.budget,
        "road_routing_offline": router.offline if router else True,
        "scope_city": req.scope_city, "max_leg_min": req.max_leg_min,
        "recommendation_strategy": "Review popularity, rating, visitor relevance and distance; rating >= 4.0",
        "recommendation_source": "Your Massachusetts dataset, September 2021 snapshot; reviews are a popularity proxy, not visitor counts",
        "travel_mode": req.travel_mode, "trip_date": req.trip_date,
        "parking_buffer_min": router.parking_min,
        "uses_google": router.used_google,
        "routing_notes": sorted(router.notes),
    }


class App:
    def __init__(self, data_dir):
        print(f"Loading businesses from {data_dir} ...", flush=True)
        self.businesses, self.stats = load_businesses(data_dir)
        self.catalog = {b.gmap_id: b for b in self.businesses}
        self.cities = {address_city(b.address) for b in self.businesses} - {""}
        self.geocoder = Geocoder()
        print(f"Loaded {self.stats['kept']} businesses.", flush=True)

    def plan(self, body):
        req, n_days, start, end = build_request(body, self.geocoder, self.cities)
        try:
            parking = int(body.get("parking_buffer_min", 5))
            if not 0 <= parking <= 60:
                raise HttpError(400, "Parking buffer must be between 0 and 60 minutes.")
            router = TripRouter(req.travel_mode, os.environ.get("GOOGLE_MAPS_API_KEY"), parking, req.trip_date)
            trip = plan_trip(self.businesses, self.catalog, req, n_days, router=router)
            return serialize_plan(trip, req, start, end, router, n_days)
        except RoutingError as exc:
            raise HttpError(503, str(exc))
        except ValueError:
            raise HttpError(400, "Invalid parking buffer.")


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt_, *args):  # keep the console quiet
            pass

        def _send(self, status, payload, content_type="application/json; charset=utf-8"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                raise HttpError(400, "request body must be JSON")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/map-config":
                # Only the website-restricted browser key is public. Never expose the Routes or Claude keys.
                self._send(200, {"browser_key": os.environ.get("GOOGLE_MAPS_BROWSER_KEY", "")})
            elif self.path in ("/terms.html", "/privacy.html"):
                self._send(200, (WEB_DIR / self.path.lstrip("/")).read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, {"error": "not found"})

        def _client(self):
            forwarded = self.headers.get("X-Forwarded-For", "")
            return forwarded.split(",")[0].strip() or self.client_address[0]

        def do_POST(self):
            try:
                body = self._read_json()
                if self.path == "/api/chat":
                    message = (body.get("message") or "").strip()
                    if not message:
                        raise HttpError(400, "type a request first")
                    if not LIMITER.allow("chat:" + self._client(), CHAT_PER_IP_PER_HOUR):
                        raise HttpError(429, "Too many chat requests from you this hour. Try again later, or fill in the form.")
                    if not LIMITER.take_daily():
                        raise HttpError(429, "The chat is full for today. Fill in the form instead, or try again tomorrow.")
                    self._send(200, call_claude_for_params(message))
                elif self.path == "/api/plan":
                    if not LIMITER.allow("plan:" + self._client(), PLAN_PER_IP_PER_HOUR):
                        raise HttpError(429, "Too many plans from you this hour. Try again later.")
                    self._send(200, app.plan(body))
                else:
                    self._send(404, {"error": "not found"})
            except HttpError as e:
                self._send(e.status, {"error": str(e)})
            except Exception as e:  # report unexpected failures to the page instead of hanging
                self._send(500, {"error": f"server error: {e}"})

    return Handler


def main(argv=None):
    p = argparse.ArgumentParser(description="Run the trip planner web page and API on this computer.")
    p.add_argument("--data", default=str(ROOT / "data" / "raw"))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = p.parse_args(argv)
    app = App(args.data)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    server.daemon_threads = True
    print(f"Open http://{args.host}:{args.port} in your browser. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
