"""Load and clean the Massachusetts Google Local business metadata.

Source: UCSD McAuley lab Google Local dataset, file meta-Massachusetts.json.gz
(one JSON object per line). Download instructions are in README.md.
"""
import gzip
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

META_FILE = "meta-Massachusetts.json.gz"
PERMANENTLY_CLOSED = "Permanently closed"
VALID_PRICES = {"$", "$$", "$$$", "$$$$"}
# Massachusetts addresses contain ", MA" before the ZIP code, e.g. "Marshfield, MA 02050",
# or spell out "Massachusetts". Many records have no address at all.
_MA_RE = re.compile(r",\s*MA\b|Massachusetts", re.IGNORECASE)
# Rough bounding box of Massachusetts. Some records have placeholder coordinates
# (e.g. 28.65, 180) that fall outside it; those are dropped as bad geocodes.
MA_LAT = (41.2, 42.9)
MA_LON = (-73.6, -69.8)


def _in_ma_box(lat, lon):
    return MA_LAT[0] <= lat <= MA_LAT[1] and MA_LON[0] <= lon <= MA_LON[1]


@dataclass(frozen=True)
class Business:
    gmap_id: str
    name: str
    address: str
    lat: float
    lon: float
    categories: tuple
    rating: float
    n_reviews: int
    price: str | None          # "$", "$$", "$$$", "$$$$" or None when not recorded
    hours: dict = field(compare=False, hash=False)  # weekday -> raw hours text or None
    url: str = ""


def _business_from_record(r):
    hours = {}
    for pair in r.get("hours") or []:
        if isinstance(pair, list) and len(pair) == 2:
            hours[pair[0]] = pair[1]
    price = r.get("price")
    return Business(
        gmap_id=r["gmap_id"],
        name=r.get("name") or "",
        address=r.get("address") or "",
        lat=float(r["latitude"]),
        lon=float(r["longitude"]),
        categories=tuple(r.get("category") or ()),
        rating=float(r.get("avg_rating") or 0.0),
        n_reviews=int(r.get("num_of_reviews") or 0),
        price=price if price in VALID_PRICES else None,
        hours=hours,
        url=r.get("url") or "",
    )


def load_businesses(data_dir="data/raw"):
    """Return (businesses, stats). Removes permanently closed, out-of-state,
    and coordinate-less records. stats counts what was dropped."""
    path = Path(data_dir) / META_FILE
    stats = {"total": 0, "permanently_closed": 0, "out_of_state": 0,
             "bad_coordinates": 0, "kept": 0}
    businesses = []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            stats["total"] += 1
            if r.get("state") == PERMANENTLY_CLOSED:
                stats["permanently_closed"] += 1
                continue
            address = r.get("address")
            if address and not _MA_RE.search(address):
                stats["out_of_state"] += 1
                continue
            lat, lon = r.get("latitude"), r.get("longitude")
            if lat is None or lon is None or not _in_ma_box(float(lat), float(lon)):
                stats["bad_coordinates"] += 1
                continue
            businesses.append(_business_from_record(r))
    stats["kept"] = len(businesses)
    return businesses, stats


def address_city(address):
    """Municipality explicitly recorded immediately before the Massachusetts state field."""
    match = re.search(r",\s*([^,]+),\s*(?:MA\b|Massachusetts\b)", address or "", re.IGNORECASE)
    return match.group(1).strip() if match else ""
