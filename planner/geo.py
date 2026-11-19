"""Distance and travel-time estimates.

v1 uses straight-line (haversine) distance times a detour factor, at an
assumed average urban driving speed. This is an estimate, not a routing result.
"""
import math

EARTH_RADIUS_KM = 6371.0
DETOUR_FACTOR = 1.3      # roads are longer than the straight line
DRIVE_SPEED_KMH = 25.0   # assumed average speed in town, including stops


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def travel_minutes(lat1, lon1, lat2, lon2):
    """Estimated travel time in minutes (not rounded)."""
    km = haversine_km(lat1, lon1, lat2, lon2) * DETOUR_FACTOR
    return km / DRIVE_SPEED_KMH * 60.0
