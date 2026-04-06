"""
explore_bus_edges.py
--------------------
Gently explores the ODPT public API for Toei Bus timetable data around
the "edge case" terminus stations identified in tube_challenge.py.

Strategy
--------
1. On first run, fetch from the ODPT public API and write to a local
   JSON cache file (datasets/odpt_bus_cache.json).
2. On subsequent runs, read from the cache — no API calls at all unless
   --refresh is passed.
3. For each priority station pair, look for matching BusTimetable entries
   and print a summary: route, stops, first/last departures.
4. Outputs a proposed add_custom_connections snippet you can paste into
   tube_challenge.py.

Usage
-----
    python scripts/explore_bus_edges.py               # use cache if present
    python scripts/explore_bus_edges.py --refresh     # force re-fetch from ODPT
    python scripts/explore_bus_edges.py --list-stops  # also dump all stops found near each station

ODPT Public API (no key required):
    https://api-public.odpt.org/api/v4/odpt:BusTimetable.json
    https://api-public.odpt.org/api/v4/odpt:BusroutePattern.json
    https://api-public.odpt.org/api/v4/odpt:Busstop.json
"""

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CACHE_PATH = os.path.join("datasets", "odpt_bus_cache.json")

# ODPT public endpoints (no API key required)
ENDPOINTS = {
    "timetables": "https://api-public.odpt.org/api/v4/odpt:BusTimetable.json",
    "patterns":   "https://api-public.odpt.org/api/v4/odpt:BusroutePattern.json",
    "stops":      "https://api-public.odpt.org/api/v4/odpt:Busstop.json",
}

# Be polite — wait between requests
REQUEST_DELAY_SECONDS = 2.0

# ---------------------------------------------------------------------------
# Priority station pairs to investigate
# Each entry: (from_station_name, to_station_name, from_code, to_code, reason)
# ---------------------------------------------------------------------------

PRIORITY_EDGES = [
    ("Tatsumi",            "Shinonome",        "Y25", "Y24", "Yurakucho dead-end branch — forces backtrack via Shin-Kiba"),
    ("Tatsumi",            "Kiba",             "Y25", "T13", "Tatsumi → Tozai shortcut candidate"),
    ("Narimasu",           "Hikarigaoka",      "Y02", "E38", "Existing bus edge — verify/improve timetable"),
    ("Nerima-Kasugacho",   "Kotake-mukaihara", "E36", "Y06", "Oedo near-terminus stub — already bridged at E35 but E36 isolated"),
    ("Shin-Egota",         "Nakai",            "E04", "E05", "Oedo near-terminus — cross to Marunouchi/Oedo"),
    ("Nishi-Magome",       "Gotanda",          "A01", "A05", "Asakusa true terminus — Tokyu Oimachi bus link"),
    ("Ayase",              "Kita-Senju",       "C19", "H22", "Chiyoda branch dead-end — Joban Line runs this in ~4 min"),
    ("Tsurukabuto",        "Sengawa",          "S03", None,  "Shinjuku near-terminus in residential area"),
]

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Remove non-alphanumeric characters and lowercase."""
    if not name:
        return ""
    name = re.sub(r"[^0-9A-Za-zぁ-んァ-ン一-龥]", "", name)
    return name.lower()


def _contains(text: str, query: str) -> bool:
    """Case-insensitive substring check."""
    return query.lower() in text.lower()


# ---------------------------------------------------------------------------
# API fetch (rate-limited)
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> list:
    """Fetch a URL and return parsed JSON (list expected)."""
    print(f"  Fetching {url} ...")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def fetch_all(endpoints: dict, delay: float = REQUEST_DELAY_SECONDS) -> dict:
    """Fetch all endpoints with a polite delay between each."""
    result = {}
    for key, url in endpoints.items():
        try:
            data = _fetch_json(url)
            result[key] = data
            print(f"  ✓ {key}: {len(data)} records")
        except Exception as e:
            print(f"  ✗ {key}: failed — {e}")
            result[key] = []
        time.sleep(delay)
    return result


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def load_cache(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        fetched_at = data.get("_fetched_at", "unknown")
        print(f"Using cache from {fetched_at} ({path})")
        return data
    except Exception as e:
        print(f"Cache read error: {e}")
        return None


def save_cache(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["_fetched_at"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Cache written → {path}")


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def find_stops_near(stops: list, station_name: str) -> list:
    """Return all bus stops whose title or dc:title contains station_name."""
    matches = []
    for stop in stops:
        titles = [
            stop.get("dc:title", ""),
            stop.get("odpt:stationTitle", {}).get("en", ""),
            stop.get("odpt:stationTitle", {}).get("ja", ""),
        ]
        if any(_contains(t, station_name) for t in titles if t):
            matches.append(stop)
    return matches


def find_patterns_through(patterns: list, stop_ids: list) -> list:
    """Return route patterns that pass through any of stop_ids."""
    stop_id_set = set(stop_ids)
    matched = []
    for pattern in patterns:
        busstops = pattern.get("odpt:busstopPoleOrder", [])
        pattern_stop_ids = [s.get("odpt:busstopPole", "") for s in busstops]
        if stop_id_set.intersection(pattern_stop_ids):
            matched.append(pattern)
    return matched


def find_timetables_for_pattern(timetables: list, pattern_id: str) -> list:
    """Return timetable entries for a given busroutePattern id."""
    return [
        t for t in timetables
        if t.get("odpt:busroutePattern", "") == pattern_id
    ]


def extract_departure_times(timetable_entry: dict) -> list[str]:
    """Extract list of departure time strings from a BusTimetable entry."""
    times = []
    for obj in timetable_entry.get("odpt:busTimetableObject", []):
        dep = obj.get("odpt:departureTime")
        if dep:
            times.append(dep)
    return times


def get_stop_order_in_pattern(pattern: dict, stop_id: str) -> int | None:
    """Return 0-based order index of stop_id in a pattern, or None."""
    for entry in pattern.get("odpt:busstopPoleOrder", []):
        if entry.get("odpt:busstopPole") == stop_id:
            return entry.get("odpt:index", None)
    return None


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyse_edge(
    from_name: str,
    to_name: str,
    from_code: str,
    to_code: str | None,
    reason: str,
    stops: list,
    patterns: list,
    timetables: list,
    list_stops: bool = False,
):
    print(f"\n{'='*60}")
    print(f"  {from_code} {from_name}  →  {to_code or '?'} {to_name}")
    print(f"  Reason: {reason}")
    print(f"{'='*60}")

    from_stops = find_stops_near(stops, from_name)
    to_stops   = find_stops_near(stops, to_name)

    if list_stops:
        print(f"\n  Bus stops matching '{from_name}':")
        for s in from_stops:
            print(f"    {s.get('@id')}  {s.get('dc:title')}")
        print(f"\n  Bus stops matching '{to_name}':")
        for s in to_stops:
            print(f"    {s.get('@id')}  {s.get('dc:title')}")

    if not from_stops:
        print(f"  ✗ No bus stops found near '{from_name}' — no bus link possible here.")
        return None
    if not to_stops:
        print(f"  ✗ No bus stops found near '{to_name}' — no bus link possible here.")
        return None

    from_ids = [s.get("@id") for s in from_stops]
    to_ids   = [s.get("@id") for s in to_stops]

    # Find patterns through FROM stop
    from_patterns = find_patterns_through(patterns, from_ids)
    if not from_patterns:
        print(f"  ✗ No route patterns pass through '{from_name}' stops.")
        return None

    # Among those, find patterns that ALSO pass through TO stop
    # AND where FROM comes before TO (direction check)
    linking_patterns = []
    for pat in from_patterns:
        pole_order = pat.get("odpt:busstopPoleOrder", [])
        pattern_stop_ids = [s.get("odpt:busstopPole", "") for s in pole_order]
        from_matches = [sid for sid in from_ids if sid in pattern_stop_ids]
        to_matches   = [sid for sid in to_ids   if sid in pattern_stop_ids]
        if not from_matches or not to_matches:
            continue
        # pick the first matching stop index for each
        from_idx = min(pattern_stop_ids.index(sid) for sid in from_matches)
        to_idx   = min(pattern_stop_ids.index(sid) for sid in to_matches)
        if from_idx < to_idx:
            linking_patterns.append((pat, from_idx, to_idx, len(pole_order)))

    if not linking_patterns:
        print(f"  ✗ No route goes from '{from_name}' toward '{to_name}'.")
        return None

    print(f"  ✓ Found {len(linking_patterns)} linking route pattern(s):\n")

    suggestions = []
    for pat, from_idx, to_idx, total_stops in linking_patterns:
        pat_id = pat.get("@id", "")
        route_title = pat.get("dc:title", pat_id)
        stop_count = to_idx - from_idx
        # estimate travel time: Tokyo buses average ~2-3 min/stop
        est_minutes = stop_count * 2.5

        # fetch timetable for first/last departure
        tts = find_timetables_for_pattern(timetables, pat_id)
        departures = []
        for tt in tts:
            departures.extend(extract_departure_times(tt))
        departures.sort()
        dep_summary = ""
        if departures:
            dep_summary = f", first dep {departures[0]}, last dep {departures[-1]}, {len(departures)} trips/day"

        print(f"    Route: {route_title}")
        print(f"    Pattern ID: {pat_id}")
        print(f"    Stops between: {stop_count} (indices {from_idx}→{to_idx} of {total_stops})")
        print(f"    Estimated travel time: ~{est_minutes:.0f} min{dep_summary}")

        if from_code and to_code:
            suggestions.append({
                "from_code": from_code,
                "to_code": to_code,
                "from_name": from_name,
                "to_name": to_name,
                "pattern_id": pat_id,
                "route_title": route_title,
                "stop_count": stop_count,
                "est_minutes": round(est_minutes, 1),
                "departures_sample": departures[:5],
                "total_trips": len(departures),
            })

    return suggestions or None


# ---------------------------------------------------------------------------
# Snippet generator
# ---------------------------------------------------------------------------

def print_snippet(all_suggestions: list):
    if not all_suggestions:
        print("\nNo new connections found to suggest.")
        return

    print("\n" + "="*60)
    print("  Suggested add_custom_connections snippet")
    print("="*60)
    print("  # Add these inside add_custom_connections() in tube_challenge.py:\n")

    for s in all_suggestions:
        w = round(s["est_minutes"] + 2, 1)  # +2 for boarding/transfer
        print(f"    # Bus: {s['from_name']} → {s['to_name']} ({s['route_title']}, ~{s['est_minutes']} min, {s['total_trips']} trips/day)")
        print(f"    graph.add_edge(\"{s['from_code']}\", \"{s['to_code']}\", real_distance=0, weight={w}, color=\"Bus\")")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Explore ODPT bus data for tube_challenge edge stations.")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch from ODPT API (ignores cache)")
    parser.add_argument("--list-stops", action="store_true", dest="list_stops", help="Print all matching bus stops for each station")
    parser.add_argument("--cache-path", default=CACHE_PATH, help=f"Path to cache file (default: {CACHE_PATH})")
    args = parser.parse_args()

    # Load or fetch data
    cache = None if args.refresh else load_cache(args.cache_path)
    if cache is None:
        print("Fetching from ODPT public API (this may take ~10s) ...")
        cache = fetch_all(ENDPOINTS)
        save_cache(args.cache_path, cache)

    stops      = cache.get("stops", [])
    patterns   = cache.get("patterns", [])
    timetables = cache.get("timetables", [])

    print(f"\nLoaded: {len(stops)} stops, {len(patterns)} route patterns, {len(timetables)} timetable entries")

    # Analyse each priority edge
    all_suggestions = []
    for (from_name, to_name, from_code, to_code, reason) in PRIORITY_EDGES:
        result = analyse_edge(
            from_name, to_name, from_code, to_code, reason,
            stops, patterns, timetables,
            list_stops=args.list_stops,
        )
        if result:
            all_suggestions.extend(result)

    # Print paste-ready snippet
    print_snippet(all_suggestions)

    # Save suggestions to JSON for later use
    if all_suggestions:
        out_path = os.path.join("datasets", "bus_edge_suggestions.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_suggestions, f, ensure_ascii=False, indent=2)
        print(f"\nSuggestions saved → {out_path}")


if __name__ == "__main__":
    main()
