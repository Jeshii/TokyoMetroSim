"""
explore_bus_edges.py
--------------------
Explores the ODPT public API (Toei Bus only) for bus links between the
"edge case" terminus stations in tube_challenge.py.

Key facts discovered:
- The ODPT public API only covers Toei Bus routes.
- The Busstop endpoint returns 404; stop names live in odpt:note fields
  inside odpt:BusroutePattern > odpt:busstopPoleOrder.
- The Narimasu ↔ Hikarigaoka bus (route 国02 / 成01) is operated by
  Kokusai Kogyo (国際興業), NOT Toei. It will never appear here.
  Manually set weight=20 in add_custom_connections as a fallback.
- The ODPT endpoints return a redirect; we follow it automatically.

Useful Toei routes found:
  白61  新江古田駅前 ↔ 練馬駅  (Shin-Egota E04 ↔ Nerima E35)

Strategy
--------
1. On first run, fetch BusroutePattern + BusTimetable and write to
   datasets/odpt_bus_cache.json.
2. On subsequent runs, read from cache (no API calls unless --refresh).
3. Match stops by substring on odpt:note (Japanese station name).
4. For each priority pair, find patterns where FROM precedes TO,
   print a summary, and emit a graph.add_edge() snippet.
5. Save suggestions to datasets/bus_edge_suggestions.json.

Usage
-----
    python scripts/explore_bus_edges.py
    python scripts/explore_bus_edges.py --refresh
    python scripts/explore_bus_edges.py --list-stops
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

# ODPT public endpoints — Busstop (404) removed; names are in BusroutePattern
ENDPOINTS = {
    "patterns":   "https://api-public.odpt.org/api/v4/odpt:BusroutePattern.json",
    "timetables": "https://api-public.odpt.org/api/v4/odpt:BusTimetable.json",
}

REQUEST_DELAY_SECONDS = 2.0

# ---------------------------------------------------------------------------
# Priority station pairs
# (from_name_ja, to_name_ja, from_code, to_code, reason)
# Names must match odpt:note field values (Japanese) in BusroutePattern.
# Narimasu/Hikarigaoka omitted — those are Kokusai Kogyo, not Toei.
# ---------------------------------------------------------------------------

PRIORITY_EDGES = [
    # Confirmed present in Toei data
    ("新江古田駅前",  "練馬駅",       "E04", "E35", "Shin-Egota → Nerima (白61, confirmed Toei)"),
    ("練馬駅",       "新江古田駅前",  "E35", "E04", "Nerima → Shin-Egota reverse (白61)"),

    # Toei coverage area — may or may not have stops
    ("辰巳駅前",     "潮見駅前",     "Y25", None,  "Tatsumi → Shiome area (Yurakucho dead end)"),
    ("辰巳一丁目",   "東陽町駅前",   "Y25", "T12", "Tatsumi area → Tozai line"),
    ("綾瀬駅前",     "北千住駅前",   "C19", "H22", "Ayase → Kita-Senju (Chiyoda branch)"),
    ("西馬込駅前",   "五反田駅前",   "A01", "A05", "Nishi-Magome → Gotanda (Asakusa terminus)"),
    ("西台駅前",     "高島平駅前",   None,  None,  "Nishidai area Mita line check"),

    # Kokusai Kogyo routes (NOT in Toei ODPT — listed here for documentation)
    # ("成増駅", "光が丘駅", "Y02", "E38", "Narimasu → Hikarigaoka — Kokusai Kogyo, not Toei"),
]

# Manual fallback weights for non-Toei routes (to use in add_custom_connections)
MANUAL_FALLBACKS = [
    {
        "from_code": "Y02", "to_code": "E38",
        "from_name": "Narimasu", "to_name": "Hikarigaoka",
        "operator": "Kokusai Kogyo (国際興業) — not in ODPT public API",
        "route": "国02 / 成01",
        "est_minutes": 20,
        "note": "Runs every ~15 min daytime. Real distance ~2.4 km but traffic-heavy. Use weight=22.",
    },
]

# ---------------------------------------------------------------------------
# HTTP helper — follows ODPT redirect transparently
# ---------------------------------------------------------------------------

def _fetch_json(url: str) -> list:
    """Fetch URL, follow one redirect if needed, return parsed JSON list."""
    print(f"  GET {url}")
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "TokyoMetroSim/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")

    # ODPT sometimes returns a plain-text redirect URL instead of a 3xx
    stripped = body.strip()
    if stripped.startswith("Found. Redirecting to "):
        redirect_url = stripped.replace("Found. Redirecting to ", "").strip()
        print(f"  → redirect → {redirect_url[:80]}...")
        req2 = urllib.request.Request(
            redirect_url,
            headers={"User-Agent": "TokyoMetroSim/1.0"},
        )
        with urllib.request.urlopen(req2, timeout=120) as resp2:
            body = resp2.read().decode("utf-8")

    return json.loads(body)


def fetch_all(endpoints: dict, delay: float = REQUEST_DELAY_SECONDS) -> dict:
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
        print(f"Using cache from {data.get('_fetched_at', 'unknown')} ({path})")
        return data
    except Exception as e:
        print(f"Cache read error: {e} — will re-fetch")
        return None


def save_cache(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["_fetched_at"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Cache written → {path}")


# ---------------------------------------------------------------------------
# Stop matching — uses odpt:note inside busstopPoleOrder
# ---------------------------------------------------------------------------

def find_patterns_with_stop(patterns: list, stop_name_ja: str) -> list[tuple]:
    """
    Return list of (pattern, pole_index, pole_entry) for patterns
    where any pole's odpt:note contains stop_name_ja as a substring.
    """
    results = []
    for pat in patterns:
        poles = pat.get("odpt:busstopPoleOrder", [])
        for pole in poles:
            note = pole.get("odpt:note", "")
            if stop_name_ja in note:
                results.append((pat, pole.get("odpt:index", 0), pole))
                break  # one match per pattern is enough
    return results


def find_timetables_for_pattern(timetables: list, pattern_id: str) -> list:
    return [t for t in timetables if t.get("odpt:busroutePattern") == pattern_id]


def extract_departures(timetable_entries: list) -> list[str]:
    times = []
    for tt in timetable_entries:
        for obj in tt.get("odpt:busTimetableObject", []):
            dep = obj.get("odpt:departureTime")
            if dep:
                times.append(dep)
    times.sort()
    return times


# ---------------------------------------------------------------------------
# Analysis per edge
# ---------------------------------------------------------------------------

def analyse_edge(
    from_ja: str, to_ja: str,
    from_code: str | None, to_code: str | None,
    reason: str,
    patterns: list, timetables: list,
    list_stops: bool = False,
) -> list | None:
    print(f"\n{'='*60}")
    print(f"  {from_code or '?'} {from_ja}  →  {to_code or '?'} {to_ja}")
    print(f"  Reason: {reason}")
    print(f"{'='*60}")

    from_hits = find_patterns_with_stop(patterns, from_ja)
    to_hits   = find_patterns_with_stop(patterns, to_ja)

    from_pat_ids = {p.get("@id") for p, _, _ in from_hits}
    to_pat_ids   = {p.get("@id") for p, _, _ in to_hits}
    linking_pat_ids = from_pat_ids & to_pat_ids

    if not from_pat_ids:
        print(f"  ✗ No Toei patterns stop at '{from_ja}'")
        return None
    if not to_pat_ids:
        print(f"  ✗ No Toei patterns stop at '{to_ja}'")
        return None
    if not linking_pat_ids:
        print(f"  ✗ No single Toei route goes from '{from_ja}' to '{to_ja}'")
        print(f"    ('{from_ja}' in {len(from_pat_ids)} patterns, '{to_ja}' in {len(to_pat_ids)} patterns — no overlap)")
        return None

    if list_stops:
        print(f"  Patterns containing '{from_ja}':")
        for p, idx, _ in from_hits:
            print(f"    [{p.get('dc:title')}] pole_index={idx}")

    suggestions = []
    for pat_id in linking_pat_ids:
        # find the pattern object
        pat = next((p for p, _, _ in from_hits if p.get("@id") == pat_id), None)
        if not pat:
            continue
        poles = pat.get("odpt:busstopPoleOrder", [])
        pole_notes = [p.get("odpt:note", "") for p in poles]

        # find first index where from_ja and to_ja appear
        from_indices = [i for i, n in enumerate(pole_notes) if from_ja in n]
        to_indices   = [i for i, n in enumerate(pole_notes) if to_ja in n]
        if not from_indices or not to_indices:
            continue
        from_idx = min(from_indices)
        to_idx   = min(to_indices)
        if from_idx >= to_idx:
            continue  # wrong direction

        stop_count  = to_idx - from_idx
        est_minutes = round(stop_count * 2.5, 1)
        route_title = pat.get("dc:title", pat_id)

        # timetable lookup
        tts         = find_timetables_for_pattern(timetables, pat_id)
        departures  = extract_departures(tts)
        dep_summary = ""
        if departures:
            dep_summary = (f", first={departures[0]}, last={departures[-1]},"
                           f" {len(departures)} trips")

        print(f"  ✓ Route: {route_title}")
        print(f"    Stops {from_ja}({from_idx}) → {to_ja}({to_idx}) = {stop_count} stops, ~{est_minutes} min{dep_summary}")

        if from_code and to_code:
            suggestions.append({
                "from_code":       from_code,
                "to_code":         to_code,
                "from_name_ja":    from_ja,
                "to_name_ja":      to_ja,
                "pattern_id":      pat_id,
                "route_title":     route_title,
                "stop_count":      stop_count,
                "est_minutes":     est_minutes,
                "departures_sample": departures[:5],
                "total_trips":     len(departures),
            })

    return suggestions or None


# ---------------------------------------------------------------------------
# Snippet generator
# ---------------------------------------------------------------------------

def print_snippet(suggestions: list, fallbacks: list):
    print("\n" + "="*60)
    print("  Suggested add_custom_connections() additions")
    print("="*60)

    if suggestions:
        print("  # From ODPT Toei Bus data:")
        for s in suggestions:
            w = round(s["est_minutes"] + 2, 1)
            print(f"    # Bus {s['route_title']}: {s['from_name_ja']} → {s['to_name_ja']}"
                  f" (~{s['est_minutes']} min, {s['total_trips']} trips/day)")
            print(f"    graph.add_edge(\"{s['from_code']}\", \"{s['to_code']}\","
                  f" real_distance=0, weight={w}, color=\"Bus\")")
            print()

    print("  # Manual fallbacks (non-Toei operators, not in ODPT public API):")
    for fb in fallbacks:
        w = round(fb["est_minutes"] + 2, 1)
        print(f"    # Bus {fb['route']} ({fb['operator']}): {fb['from_name']} → {fb['to_name']}")
        print(f"    # {fb['note']}")
        print(f"    graph.add_edge(\"{fb['from_code']}\", \"{fb['to_code']}\","
              f" real_distance=2.4, weight={w}, color=\"Bus\")")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Explore ODPT Toei Bus data for tube_challenge edge stations."
    )
    parser.add_argument("--refresh",    action="store_true", help="Force re-fetch from API")
    parser.add_argument("--list-stops", action="store_true", dest="list_stops",
                        help="Print all matching patterns per station")
    parser.add_argument("--cache-path", default=CACHE_PATH)
    args = parser.parse_args()

    cache = None if args.refresh else load_cache(args.cache_path)
    if cache is None:
        print("Fetching from ODPT public API ...")
        cache = fetch_all(ENDPOINTS)
        save_cache(args.cache_path, cache)

    patterns   = cache.get("patterns", [])
    timetables = cache.get("timetables", [])
    print(f"\nLoaded: {len(patterns)} route patterns, {len(timetables)} timetable entries")
    print("Note: ODPT public API covers Toei Bus only.")
    print("      Narimasu↔Hikarigaoka (Kokusai Kogyo) will not appear here.\n")

    all_suggestions = []
    for (from_ja, to_ja, from_code, to_code, reason) in PRIORITY_EDGES:
        result = analyse_edge(
            from_ja, to_ja, from_code, to_code, reason,
            patterns, timetables,
            list_stops=args.list_stops,
        )
        if result:
            all_suggestions.extend(result)

    print_snippet(all_suggestions, MANUAL_FALLBACKS)

    # Save
    out = {"odpt_suggestions": all_suggestions, "manual_fallbacks": MANUAL_FALLBACKS}
    out_path = os.path.join("datasets", "bus_edge_suggestions.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Suggestions saved → {out_path}")


if __name__ == "__main__":
    main()
