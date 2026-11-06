"""Safety-first route ranking.

Inputs per route: distance_km, duration_min, coordinates [[lat, lng], ...].
Each route is scored using
  * exposure to accident-prone stations (multi-year 2018-2025 data),
  * live traffic congestion sampled along the route (TomTom Traffic Flow API,
    used when TOMTOM_API_KEY is set; otherwise a time-of-day estimate),
  * travel time and distance.
Traffic details are used only for the decision and are not returned.
"""
import math
import os
from concurrent.futures import ThreadPoolExecutor
import requests

def _load_local_env():
    """Read KEY=VALUE lines from a local .env file next to this script."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_local_env()
TOMTOM_KEY = os.environ.get("TOMTOM_API_KEY", "").strip()
FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
_cache = {}


def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _sample(coords, n):
    if len(coords) <= n:
        return coords
    step = (len(coords) - 1) / (n - 1)
    return [coords[round(i * step)] for i in range(n)]


def _live_congestion(point):
    """Return ratio freeFlow/current speed (>=1 means slower than normal) or None."""
    key = (round(point[0], 3), round(point[1], 3))
    if key in _cache:
        return _cache[key]
    value = None
    try:
        r = requests.get(FLOW_URL, params={"point": f"{point[0]},{point[1]}", "key": TOMTOM_KEY,
                                           "unit": "KMPH"}, timeout=4)
        if r.ok:
            d = r.json().get("flowSegmentData", {})
            cur, free = float(d.get("currentSpeed", 0)), float(d.get("freeFlowSpeed", 0))
            if d.get("roadClosure"):
                value = 4.0
            elif cur > 0 and free > 0:
                value = max(1.0, min(4.0, free / cur))
    except (requests.RequestException, ValueError):
        value = None
    _cache[key] = value
    return value


def _route_congestion(coords, fallback):
    if not TOMTOM_KEY:
        return fallback
    points = _sample(coords, 6)
    with ThreadPoolExecutor(max_workers=6) as pool:
        values = [v for v in pool.map(_live_congestion, points) if v is not None]
    return sum(values) / len(values) if values else fallback


def _risk_exposure(coords, stations):
    """Sum of station risk scores weighted by how close the route passes (within 1.5 km)."""
    pts = _sample(coords, 80)
    total = 0.0
    for _, s in stations.iterrows():
        loc = (s["latitude"], s["longitude"])
        d = min(_haversine_km(p, loc) for p in pts)
        if d < 1.5:
            total += s["risk_score"] * (1 - d / 1.5)
    return total


def analyse_routes(routes, stations, time_multiplier):
    evaluated = []
    for index, route in enumerate(routes):
        distance = float(route.get("distance_km", 0))
        duration = float(route.get("duration_min", 0))
        coords = route.get("coordinates") or []
        if distance <= 0 or duration <= 0 or distance > 1000 or duration > 10000 or len(coords) < 2:
            continue
        coords = [(float(c[0]), float(c[1])) for c in coords[:5000]]
        congestion = _route_congestion(coords, time_multiplier)
        eta = duration * congestion
        exposure = _risk_exposure(coords, stations)
        evaluated.append({"route_index": index, "distance_km": round(distance, 1),
                          "estimated_duration_min": round(eta), "_exp": exposure,
                          "_cong": congestion, "_eta": eta})
    if not evaluated:
        return []
    max_exp = max(e["_exp"] for e in evaluated) or 1
    min_eta = min(e["_eta"] for e in evaluated)
    for e in evaluated:
        risk_part = e["_exp"] / max_exp                 # 0..1 accident exposure
        time_part = e["_eta"] / min_eta - 1             # extra time vs fastest
        cong_part = min(1.0, (e["_cong"] - 1) / 1.5)    # heavy congestion -> more conflicts
        e["score"] = round(0.55 * risk_part + 0.25 * time_part + 0.20 * cong_part, 4)
        e["safety_score"] = max(1, min(100, round(100 - 60 * risk_part - 25 * cong_part - 15 * min(1, time_part))))
    evaluated.sort(key=lambda x: x["score"])
    for rank, e in enumerate(evaluated, start=1):
        e["rank"] = rank
        e["category"] = "safest" if rank == 1 else ("alternative" if rank <= 3 else "other")
        for k in ("_exp", "_cong", "_eta"):
            e.pop(k)
    return evaluated


def live_traffic_for_points(points, fallback_ratio):
    """Return [(ratio, source), ...] for each (lat, lng) point.

    ratio = freeFlowSpeed / currentSpeed (1.0 = free flowing, higher = more congested).
    source is "live" when TomTom answered, otherwise "estimate" (time-of-day fallback).
    """
    if not TOMTOM_KEY:
        return [(fallback_ratio, "estimate")] * len(points)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(_live_congestion, points))
    return [(v, "live") if v is not None else (fallback_ratio, "estimate") for v in values]
