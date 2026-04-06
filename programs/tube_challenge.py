import argparse
import json
import os
import glob
import re
from datetime import datetime, timedelta, date, time
import random
import heapq
import networkx as nx
from networkx.algorithms.approximation import traveling_salesman_problem

# implement all translation maps
FILE_PATH = "datasets/secondary.json"

LETTER_TO_LINE = {
    "A": "Asakusa",
    "I": "Mita",
    "S": "Shinjuku",
    "E": "Oedo",
    "G": "Ginza",
    "M": "Marunouchi",
    "H": "Hibiya",
    "T": "Tozai",
    "C": "Chiyoda",
    "Y": "Yurakucho",
    "Z": "Hanzomon",
    "N": "Namboku",
    "F": "Fukutoshin",
}

LINE_COLORS = {
    "Asakusa": "#BB3032",
    "Mita": "#3568A2",
    "Shinjuku": "#A6B24D",
    "Oedo": "#A02759",
    "Ginza": "#DA9C41",
    "Marunouchi": "#BB3032",
    "Hibiya": "#BEB8AA",
    "Tozai": "#0BA3D8",
    "Chiyoda": "#0BA3D8",
    "Yurakucho": "#BB9E64",
    "Hanzomon": "#7F74A5",
    "Namboku": "#5EAA8F",
    "Fukutoshin": "#89593A",
    "JR": "#047101",
    "Rinkai": "#2E3B7E",
    "Bus": "#FF00F7",
    "Seibu": "#40A5AF",
    "Transfer": "#00FFFF",
    "Unknown": "#cccccc",
}

# World record stored as a timedelta (single source of truth)
WORLD_RECORD_DELTA = timedelta(hours=13, minutes=53, seconds=25)
# Derived minutes for comparisons (used as default threshold)
WORLD_RECORD_MINUTES = int(WORLD_RECORD_DELTA.total_seconds() / 60)


def format_timedelta_hms(td: timedelta) -> str:
    """Format a timedelta as 'Hh Mm Ss' (omit seconds if zero)."""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if seconds:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{hours}h {minutes}m"


def get_board_departure_time(leg_idx, edge_lines, trip_ids, depart_times, arrival_times):
    """Find the index of the boarding departure for the continuous same-line run
    ending at leg_idx. Returns the index into depart_times to use as board_depart.
    
    Fixes:
    - Breaks the backwards walk on None edge_lines (not just line mismatches)
    - Unified logic used by both the summary printer and verbose leg printer
    """
    # Walk backwards to find start of contiguous same-line run
    j = leg_idx
    target_line = None
    start_k = None
    while j >= 0:
        line_j = edge_lines[j] if j < len(edge_lines) else None
        # Stop on None (gap in data) or a different line
        if line_j is None:
            break
        if line_j not in LINE_COLORS:
            break
        if target_line is None:
            target_line = line_j
            start_k = j
        elif line_j == target_line:
            start_k = j
        else:
            break
        j -= 1

    if start_k is not None:
        cand_start = start_k
        cand_end = leg_idx
    else:
        cand_start = leg_idx
        cand_end = leg_idx

    # Prefer same trip_id, then earliest depart_time, then earliest arrival_time
    current_trip = trip_ids[leg_idx] if leg_idx < len(trip_ids) else None
    chosen = None
    if current_trip:
        for j in range(cand_start, cand_end + 1):
            if j < len(trip_ids) and trip_ids[j] == current_trip:
                chosen = j
                break
    if chosen is None:
        for j in range(cand_start, cand_end + 1):
            if j < len(depart_times) and depart_times[j] is not None:
                chosen = j
                break
    if chosen is None:
        for j in range(cand_start, cand_end + 1):
            if j < len(arrival_times) and arrival_times[j] is not None:
                chosen = j
                break

    board_idx = chosen if chosen is not None else leg_idx

    # Resolve to an actual datetime
    board_depart = None
    if board_idx < len(depart_times):
        board_depart = depart_times[board_idx]
    if not board_depart and board_idx < len(arrival_times):
        board_depart = arrival_times[board_idx]

    return board_depart

def visualize_route(graph, route, positions):
    import matplotlib.pyplot as plt

    # ensure any previous figures are closed so the viewer shows the fresh image
    plt.close("all")
    fig = plt.figure(figsize=(16, 12))

    # Load and display the schematic map image
    img = plt.imread("datasets/9859zh-202305_number_en.png")
    xmin, xmax = 0, 2500
    ymin, ymax = 0, 1600
    plt.imshow(img, extent=[xmin, xmax, ymin, ymax], zorder=0)

    # Set axis limits to match image
    plt.xlim(xmin, xmax)
    plt.ylim(ymin, ymax)

    # Remove axes and whitespace
    plt.axis("off")
    plt.tight_layout(pad=0)

    # Draw the full graph with transparency
    nx.draw(
        graph,
        pos=positions,
        node_size=30,
        edge_color="lightgray",
        with_labels=False,
        alpha=0.1,
    )

    # Highlight the route with line colors
    route_edges = list(zip(route, route[1:]))
    edge_colors = []
    for u, v in route_edges:
        edge = graph.get_edge_data(u, v)
        line = edge.get("color", "Unknown") if edge else "Unknown"
        if isinstance(line, str) and line.startswith("jreast-"):
            color_key = "JR"
        else:
            color_key = line
        edge_colors.append(LINE_COLORS.get(color_key, "#cccccc"))

    nx.draw_networkx_nodes(
        graph, pos=positions, nodelist=route, node_color="red", node_size=80, alpha=0.1
    )
    nx.draw_networkx_edges(
        graph,
        pos=positions,
        edgelist=route_edges,
        edge_color=edge_colors,
        width=3,
        alpha=0.8,
    )

    # Mark U-turns and transfers
    for idx in range(1, len(route) - 1):
        prev_station = route[idx - 1]
        curr_station = route[idx]
        next_station = route[idx + 1]
        curr_line = LETTER_TO_LINE.get(curr_station[0], "Unknown Line")
        next_line = LETTER_TO_LINE.get(next_station[0], "Unknown Line")
        is_transfer = curr_line != next_line
        is_uturn = prev_station == next_station
        if is_transfer or is_uturn:
            x, y = positions.get(curr_station, (None, None))
            if x is not None and y is not None:
                plt.scatter(
                    x,
                    y,
                    c="cyan" if is_transfer else "orange",
                    s=200,
                    marker="*",
                    zorder=10,
                    alpha=0.6,
                )
                plt.text(
                    x,
                    y,
                    "T" if is_transfer else "U",
                    fontsize=14,
                    color="black",
                    ha="center",
                    va="center",
                    alpha=1.0,
                )

    # Label start/end
    start, end = route[0], route[-1]
    nx.draw_networkx_labels(
        graph,
        positions,
        labels={start: "Start", end: "End"},
        font_color="blue",
        alpha=0.9,
    )
    plt.title("Optimized Tokyo Metro Route (Schematic)")
    # save a copy so external viewers can load the latest render
    try:
        out_path = os.path.join("datasets", "last_route.png")
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
    except Exception:
        pass
    plt.show()
    plt.close(fig)


def simulate_grand_tour(graph, secondary, start_node=None, rng=None):
    """
    Simulate a grand tour of the Tokyo Metro starting from a given station.
    :param graph: The metro graph.
    :param start_node: Optional node code to anchor the route start.
    :param rng: Optional random.Random instance for reproducible random starts.
    :return: A list of stations in the tour.
    """
    unique_nodes = get_unique_station_nodes(graph, secondary)
    route = traveling_salesman_problem(
        graph, cycle=False, weight="weight", nodes=unique_nodes
    )
    # If a forced start node was provided, rotate to it
    if start_node and start_node in route:
        idx = route.index(start_node)
        route = route[idx:] + route[:idx]
    elif rng is not None:
        # No forced start — rotate to a random node in the route for diversity
        idx = rng.randint(0, len(route) - 1)
        route = route[idx:] + route[:idx]
    return route


def add_custom_connections(graph, disable_bus=False):
    # Chuo Line between Nakano and Ogikubo - one transfer plus 2 stations
    graph.add_edge("T01", "M01", real_distance=4.5, weight=8.5, color="jreast-chuo")

    # Chuo Sobu Line between Nishi-Funabashi and Motoyawata - one transfer plus one extra station
    graph.add_edge("T23", "S21", real_distance=3.4, weight=6.4, color="jreast-chuosobulocal")

    # Keiyo Line between Shin-Kiba and Hatchobori - two connections so plus 4
    graph.add_edge("Y24", "H12", real_distance=13.3, weight=17.3, color="jreast-keiyo")

    # Bus between Narimasu and Hikarigaoka - one transfer plus 9 stops
    if not disable_bus:
        graph.add_edge("Y02", "E38", real_distance=2.4, weight=22.0, color="Bus")

    graph.add_edge("Y02", "E38", real_distance=2.4, weight=12.0, color="Bike")
    graph.add_edge("Y24", "E20", real_distance=1.8, weight=10.0, color="Bike")  # to Tatsumi

    # Tokyu Toyoko: Shibuya to Jiyugaoka (bridges south gap)
    graph.add_edge("Z01", "N03", real_distance=5.0, weight=9.0, color="tokyu-toyoko")

    # Tokyu Den-en-toshi: Z01 → Futako-tamagawa
    graph.add_edge("Z01", "N04", real_distance=7.0, weight=12.0, color="tokyu-denentoshi")

    # Toei Shinjuku western end: Shinjuku (M08/S06) to Hatagaya or Sasazuka area
    graph.add_edge("M08", "S06", real_distance=0.3, weight=2.0, color="Transfer")


    # Yamanote Junctions (needs double checking)

    # Yamanote Line between Ikebukuro and Takadanobaba - one transfer plus 2 stops
    graph.add_edge("Y09", "T03", real_distance=2.0, weight=4.0, color="jreast-yamanote")
    # Yamanote Line between Takadanobaba and Shinjuku - one transfer plus 2 stops
    graph.add_edge("T03", "M08", real_distance=1.8, weight=3.8, color="jreast-yamanote")
    # Yamanote Line between Shinjuku and Yoyogi - one transfer plus 1 stops
    graph.add_edge("M08", "E26", real_distance=1.2, weight=2.2, color="jreast-yamanote")
    # Yamanote Line between Yoyogi and Shibuya - one transfer plus 1 stops
    graph.add_edge("E26", "G01", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Shibuya and Ebisu - one transfer plus 1 stops
    graph.add_edge("G01", "H02", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Ebisu and Meguro - one transfer plus 1 stops
    graph.add_edge("H02", "N01", real_distance=1.2, weight=2.2, color="jreast-yamanote")
    # Yamanote Line between Meguro and Gotanda - one transfer plus 1 stops
    graph.add_edge("N01", "A05", real_distance=1.5, weight=2.5, color="jreast-yamanote")
    # Yamanote Line between Shinbashi and Yurakucho - one transfer plus 1 stops
    graph.add_edge("A10", "Y18", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Yurakucho and Tokyo - one transfer plus 1 stops
    graph.add_edge("Y18", "M17", real_distance=1.2, weight=2.2, color="jreast-yamanote")
    # Yamanote Line between Tokyo and Kanda - one transfer plus 1 stops
    graph.add_edge("M17", "G13", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Kanda and Akihabara - one transfer plus 1 stops
    graph.add_edge("G13", "H16", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Akihabara and Ueno - one transfer plus 1 stops
    graph.add_edge("H16", "H18", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Ueno and Nishi-Nippori - one transfer plus 1 stops
    graph.add_edge("H18", "C16", real_distance=1.0, weight=2.0, color="jreast-yamanote")

    # Fill missing segments and same-station connectors reported by user
    # South-arc bridge (Gotanda -> Shinbashi) — several JR stops, approximate
    graph.add_edge("A05", "A10", real_distance=6.0, weight=10.0, color="jreast-yamanote")

    # Ueno cluster: connect Hibiya Ueno-Hirokoji (H18) to Nippori (C17) and JR Ueno nodes
    graph.add_edge("H18", "C17", real_distance=1.2, weight=3.0, color="JR")
    graph.add_edge("G16", "H18", real_distance=0.6, weight=3.0, color="JR")
    graph.add_edge("N09", "H18", real_distance=0.6, weight=3.0, color="JR")

    # Nishi-Nippori -> Komagome (Tabata area lacking metro connection) bridge
    graph.add_edge("C16", "N14", real_distance=3.5, weight=7.0, color="jreast-yamanote")

    # Ikebukuro internal same-station links (Marunouchi <-> Yurakucho, Yurakucho <-> Fukutoshin)
    graph.add_edge("M25", "Y09", real_distance=0.2, weight=3.0, color="Transfer")
    graph.add_edge("Y09", "F09", real_distance=0.2, weight=3.0, color="Transfer")

    # Yamanote Line between Komagome and Sugamo - one transfer plus 1 stops
    graph.add_edge("N14", "I15", real_distance=1.0, weight=2.0, color="jreast-yamanote")
    # Yamanote Line between Sugamo and Ikebukuro - one transfer plus 1 stops
    graph.add_edge("I15", "M25", real_distance=1.0, weight=2.0, color="jreast-yamanote")

    # User-requested additional connections and matching timetable keys
    # Seibu Yurakucho: Kotake-mukaihara (Y06 / F06) -> Nerima (E35)
    graph.add_edge("Y06", "E35", real_distance=3.0, weight=6.0, color="seibu-syurakucho")
    graph.add_edge("F06", "E35", real_distance=3.0, weight=6.0, color="seibu-syurakucho")

    # Yurikamome: Shiodome (E19) -> Toyosu (Y22)
    graph.add_edge("E19", "Y22", real_distance=4.0, weight=8.0, color="yurikamome-yurikamome")

    # Rinkai Line: Shin-kiba (Y24) -> Nakanobu (A03)
    graph.add_edge("Y24", "A03", real_distance=6.0, weight=10.0, color="twr-rinkai")

    # Tobu Skytree: connect Kita-senju (H22/C18) -> Asakusa (G19/A18)
    graph.add_edge("H22", "G19", real_distance=12.0, weight=18.0, color="tobu-tobuskytree")
    graph.add_edge("C18", "A18", real_distance=0.5, weight=3.0, color="tobu-tobuskytree")

    graph.add_edge("H01", "Z01", real_distance=0.5, weight=3.0, color="tokyu-toyoko")

    return graph


def _norm(name: str) -> str:
    """Normalize station names for fuzzy matching between datasets.
    Removes angle-bracket annotations and non-alphanumeric characters, lowercases.
    """
    if not name:
        return ""
    # remove <...> annotations
    name = re.sub(r"<.*?>", "", name)
    # keep only alphanumeric characters
    name = re.sub(r"[^0-9A-Za-z]", "", name)
    return name.lower()


def load_timetables(timetables_dir="datasets/timetables"):
    """Load all timetable JSON files into structured objects.

    Returns a dict: filename -> list of trips where each trip contains:
      - id: trip id
      - station_idx: {norm_station: index}
      - station_time: {norm_station: "HH:MM"}
    """
    timetables = {}
    files = glob.glob(os.path.join(timetables_dir, "*.json"))
    for fp in files:
        try:
            with open(fp, "r") as f:
                data = json.load(f)
        except Exception:
            continue
        trips = []
        for trip in data:
            tt = trip.get("tt", [])
            station_idx = {}
            station_time = {}
            for idx, stop in enumerate(tt):
                s = stop.get("s")
                if not s:
                    continue
                parts = s.split(".")
                station_id = parts[-1]
                # handle numeric suffixes like 'Tochomae.1' -> use previous segment
                if station_id.isdigit() and len(parts) >= 2:
                    station_id = parts[-2]
                norm = _norm(station_id)
                # prefer departure time 'd', fall back to arrival 'a'
                tstr = stop.get("d", stop.get("a"))
                if tstr:
                    station_idx[norm] = idx
                    station_time[norm] = tstr
            if station_idx:
                trips.append({
                    "id": trip.get("id"),
                    "station_idx": station_idx,
                    "station_time": station_time,
                })
        timetables[os.path.basename(fp)] = trips
    return timetables


def _find_timetable_file_for_line(line_name: str, timetables: dict):
    """Find a timetable filename key that matches the given line name.
    Uses substring matching against filenames.
    """
    if not line_name:
        return None
    line_l = line_name.lower()
    for fname in timetables.keys():
        if line_l in fname.lower():
            return fname
    return None


def _parse_time_with_date(time_str: str, base_date: date):
    try:
        h, m = map(int, time_str.split(":"))
        dt = datetime.combine(base_date, time(0, 0)) + timedelta(hours=h, minutes=m)
        return dt
    except Exception:
        return None


def find_next_trip_for_segment(timetable_trips, from_norm, to_norm, earliest_dt):
    if not timetable_trips:
        return None, None, None
    base_date = earliest_dt.date()
    candidates = []
    for trip in timetable_trips:
        sidx = trip.get("station_idx", {})
        stime = trip.get("station_time", {})
        if from_norm in sidx and to_norm in sidx and sidx[from_norm] < sidx[to_norm]:
            dep_str = stime.get(from_norm)
            arr_str = stime.get(to_norm)
            if not dep_str or not arr_str:
                continue
            dep_dt = _parse_time_with_date(dep_str, base_date)
            arr_dt = _parse_time_with_date(arr_str, base_date)
            if not dep_dt or not arr_dt:
                continue
            if arr_dt < dep_dt:
                arr_dt += timedelta(days=1)
            candidates.append((dep_dt, arr_dt, trip.get("id")))

    candidates.sort(key=lambda x: x[0])

    # *** FIX: cap lookahead to 24 hours ***
    max_wait = earliest_dt + timedelta(hours=24)
    after = [
        (dep, arr, tid) for (dep, arr, tid) in candidates
        if dep >= earliest_dt and dep <= max_wait   # <-- add the cap
    ]
    if after:
        best = min(after, key=lambda x: x[1])
        return best

    # No same-day departure — try next-day (also capped)
    if earliest_dt.hour >= 23:
        next_day = [
            (dep + timedelta(days=1), arr + timedelta(days=1), tid)
            for (dep, arr, tid) in candidates
            if (dep + timedelta(days=1)) >= earliest_dt
               and (dep + timedelta(days=1)) <= max_wait  # <-- cap here too
        ]
        if next_day:
            best = min(next_day, key=lambda x: x[1])
            return best

    return None, None, None


def find_first_departure_from_station(timetable_trips, from_norm, cutoff_dt):
    """Return the first departure datetime from `from_norm` on or after `cutoff_dt`.

    Returns (depart_dt, trip_id) or (None, None).
    """
    if not timetable_trips:
        return None, None
    base_date = cutoff_dt.date()
    candidates = []
    for trip in timetable_trips:
        stime = trip.get("station_time", {})
        if from_norm in stime:
            dep_str = stime.get(from_norm)
            if not dep_str:
                continue
            dep_dt = _parse_time_with_date(dep_str, base_date)
            if not dep_dt:
                continue
            candidates.append((dep_dt, trip.get("id")))

    candidates.sort(key=lambda x: x[0])
    for dep_dt, tid in candidates:
        if dep_dt >= cutoff_dt:
            return dep_dt, tid
    # No departure found after cutoff — return the earliest known departure
    # (it's probably just before cutoff, e.g. a 03:45 train; caller will handle)
    if candidates:
        dep_dt, tid = candidates[0]
        return dep_dt, tid  # don't add a day
    return None, None


def compute_timed_route(route, graph, secondary, timetables, start_dt, transfer_buffer_minutes=2):
    """Compute depart/arrival datetimes for each node along the route.

    Returns dict with keys:
      - depart_times: list length len(route)-1 (departure from node i to i+1)
      - arrival_times: list length len(route) (arrival at node i)
      - edge_lines: list length len(route)-1 (line used for each edge)
    """
    # If route is empty, return empty timed structure
    if not route:
        return {
            "route": [],
            "depart_times": [],
            "arrival_times": [],
            "edge_lines": [],
            "trip_ids": [],
        }

    # Expand legs that are not direct edges into shortest paths so
    # consecutive nodes in `route` are adjacent in the graph. This
    # ensures intermediate stations (like Ayase) that appear on the
    # path are accounted for in timing and visit order.
    expanded = [route[0]]
    for i in range(len(route) - 1):
        u = route[i]
        v = route[i + 1]
        try:
            if graph.has_edge(u, v):
                expanded.append(v)
            else:
                path = nx.shortest_path(graph, u, v, weight="weight")
                if len(path) >= 2:
                    expanded.extend(path[1:])
                else:
                    expanded.append(v)
        except Exception:
            # If shortest path fails for some reason, fall back
            expanded.append(v)

    # Use the expanded route for timing computations
    route = expanded
    depart_times = [None] * (len(route) - 1)
    arrival_times = [None] * len(route)
    edge_lines = [None] * (len(route) - 1)
    trip_ids = [None] * (len(route) - 1)

    arrival_times[0] = start_dt
    prev_line = None
    base_date = start_dt.date()

    for i in range(len(route) - 1):
        u = route[i]
        v = route[i + 1]
        prev_station = route[i - 1] if i - 1 >= 0 else None
        is_uturn = prev_station == v
        edge = graph.get_edge_data(u, v)
        # edge can sometimes be a dict of dicts for MultiGraph; try to normalize
        if isinstance(edge, dict) and "color" not in edge and edge:
            # pick the first nested dict
            first = next(iter(edge.values()))
            edge = first if isinstance(first, dict) else edge

        line = edge.get("color") if edge else None
        edge_lines[i] = line

        # earliest possible departure is arrival at u,
        # plus transfer buffer if changing lines
        earliest = arrival_times[i]
        if earliest is None:
            earliest = start_dt
        if prev_line and line != prev_line:
            earliest = earliest + timedelta(minutes=transfer_buffer_minutes)

        depart_dt = None
        arrive_dt = None

        # try timetable-based lookup
        tt_file = _find_timetable_file_for_line(line, timetables)
        if tt_file:
            trips = timetables.get(tt_file, [])
            from_name = secondary.get(u, None)
            to_name = secondary.get(v, None)
            from_norm = _norm(from_name)
            to_norm = _norm(to_name)
            dep_dt, arr_dt, tid = find_next_trip_for_segment(trips, from_norm, to_norm, earliest)
            if dep_dt and arr_dt:
                depart_dt = dep_dt
                arrive_dt = arr_dt
            trip_ids[i] = tid

        # fallback to edge weight (minutes)
        if depart_dt is None or arrive_dt is None:
            # use edge weight (minutes) if available
            weight = None
            if edge:
                weight = edge.get("weight") or edge.get("real_distance")
            try:
                minutes = float(weight) if weight is not None else 3.0
            except Exception:
                minutes = 3.0
            depart_dt = earliest
            arrive_dt = depart_dt + timedelta(minutes=minutes)

        # enforce a minimum boarding time for transfers or U-turns to avoid zero-minute
        min_boarding = timedelta(minutes=1)
        if (prev_line and line != prev_line) or is_uturn:
            if arrival_times[i]:
                min_needed = arrival_times[i] + min_boarding
                # if the scheduled departure is before min_needed, push forward
                if depart_dt <= arrival_times[i] or depart_dt < min_needed:
                    # if this leg was timetable-based, preserve travel duration
                    if tt_file and dep_dt and arr_dt:
                        travel_dur = arrive_dt - depart_dt
                        depart_dt = max(depart_dt, min_needed)
                        arrive_dt = depart_dt + travel_dur
                    else:
                        # fallback: use the edge-estimated minutes
                        depart_dt = max(depart_dt, min_needed)
                        arrive_dt = depart_dt + timedelta(minutes=minutes)

        depart_times[i] = depart_dt
        arrival_times[i + 1] = arrive_dt
        prev_line = line

    return {
        "route": route,
        "depart_times": depart_times,
        "arrival_times": arrival_times,
        "edge_lines": edge_lines,
        "trip_ids": trip_ids,
    }


def perturb_graph_weights(graph, noise, rng=None):
    """Return a copy of graph with edge 'weight' perturbed by up to +/- noise fraction.

    `rng` should be an instance of random.Random for reproducibility.
    """
    if rng is None:
        rng = random.Random()
    G = graph.copy()
    for u, v, data in G.edges(data=True):
        w = data.get("weight") if data.get("weight") is not None else data.get("real_distance")
        try:
            w = float(w) if w is not None else 3.0
        except Exception:
            w = 3.0
        factor = 1.0 + rng.uniform(-noise, noise)
        new_w = max(0.1, w * factor)
        data["weight"] = new_w
    return G


def total_minutes_from_timed(timed):
    """Compute total minutes for a timed route result (None if incomplete)."""
    depart_times = timed.get("depart_times")
    arrival_times = timed.get("arrival_times")
    if not arrival_times:
        return None
    start_of_trip = None
    if depart_times and depart_times[0]:
        start_of_trip = depart_times[0]
    else:
        start_of_trip = arrival_times[0]
    final_arrival = arrival_times[-1]
    if not start_of_trip or not final_arrival:
        return None
    delta = final_arrival - start_of_trip
    return int(delta.total_seconds() / 60)


def two_opt(route, graph, secondary, timetables, start_dt, max_iters=200, rng=None):
    """Perform a two-opt local search guided by static shortest-path weights."""
    if rng is None:
        rng = random.Random()

    dist_cache = {}

    def dist(u, v):
        key = (u, v)
        if key in dist_cache:
            return dist_cache[key]
        try:
            d = nx.shortest_path_length(graph, u, v, weight="weight")
        except Exception:
            d = float("inf")
        dist_cache[key] = d
        return d

    n = len(route)
    if n < 4:
        return route, compute_timed_route(route, graph, secondary, timetables, start_dt)

    current_timed = compute_timed_route(route, graph, secondary, timetables, start_dt)
    current_total = total_minutes_from_timed(current_timed) or float("inf")

    iters = 0
    improved = True
    while improved and iters < max_iters:
        improved = False
        iters += 1
        tries = max(10, n // 10)
        for _ in range(tries):
            i = rng.randint(0, n - 4)
            j = rng.randint(i + 1, n - 2)
            A, B = route[i], route[i + 1]
            C, D = route[j], route[j + 1]
            wAB, wCD, wAC, wBD = dist(A, B), dist(C, D), dist(A, C), dist(B, D)
            if any(x == float("inf") for x in (wAB, wCD, wAC, wBD)):
                continue
            if wAC + wBD + 1e-6 < wAB + wCD:
                candidate = route[:i + 1] + list(reversed(route[i + 1:j + 1])) + route[j + 1:]
                timed_candidate = compute_timed_route(candidate, graph, secondary, timetables, start_dt)
                total_candidate = total_minutes_from_timed(timed_candidate)
                if total_candidate is not None and total_candidate < current_total:
                    route = candidate
                    current_total = total_candidate
                    current_timed = timed_candidate
                    improved = True
                    # FIX: don't break — continue trying more swaps this iteration
    return route, current_timed


def load_graph(verbose=False, disable_bus=False):
    graph = nx.read_graphml("datasets/tokyometro.graphml")
    if verbose:
        print(
            "Loaded graph with",
            graph.number_of_nodes(),
            "nodes and",
            graph.number_of_edges(),
            "edges.",
        )
    if graph.number_of_nodes() == 0 or graph.number_of_edges() == 0:
        raise ValueError("Graph is empty! Check your graphml file.")

    # Custom connections - weight is time in minutes
    graph = add_custom_connections(graph, disable_bus=disable_bus)

    return graph


def get_station_to_nodes(graph, secondary):
    station_to_nodes = {}
    for node in graph.nodes():
        station_name = secondary.get(node, "Unknown Station")
        station_to_nodes.setdefault(station_name, []).append(node)
    return station_to_nodes


def get_unique_station_nodes(graph, secondary):
    station_to_nodes = get_station_to_nodes(graph, secondary)
    # Pick the first node for each station
    unique_nodes = [nodes[0] for nodes in station_to_nodes.values()]
    return unique_nodes


def main(args):

    with open(FILE_PATH, "r") as file:
        secondary = json.load(file)

    """with open("datasets/full_intersections.json", "r") as f:
        positions_data = json.load(f)

    # Build a dict: node -> (x, y)
    positions = {}
    for station_nodes in positions_data.values():
        for node, coords in station_nodes.items():
            positions[node] = (coords[0], coords[1])"""

    with open("datasets/station_positions.json", "r") as f:
        positions_data = json.load(f)

    # Image dimensions
    ymin, ymax = 200, 1550

    best_endless_candidate = None

    ys = [coords[1] for coords in positions_data.values()]
    min_y = min(ys)
    max_y = max(ys)

    positions = {}
    for node, coords in positions_data.items():
        x = coords[0]
        # Scale and flip y to match image
        y = ymax - ((coords[1] - min_y) / (max_y - min_y) * (ymax - ymin))
        positions[node] = (x, y)

    # load metro graph
    try:
        graph = load_graph(args.verbose, disable_bus=getattr(args, "no_bus", False))
    except Exception as e:
        print("Error loading graph:", e)
        return

    # load timetables
    timetables = load_timetables()

    # Optional forced start station (node code or station name)
    forced_start_node = None
    requested_start = getattr(args, "start_station", None)
    if requested_start:
        # if user provided a node code that exists in secondary, use it
        if requested_start in secondary:
            forced_start_node = requested_start
        else:
            # try to match by station name (normalized)
            station_map = get_station_to_nodes(graph, secondary)
            for name, nodes in station_map.items():
                if _norm(name) == _norm(requested_start):
                    forced_start_node = nodes[0]
                    break
            if not forced_start_node:
                # fallback to substring match
                for name, nodes in station_map.items():
                    if requested_start.lower() in name.lower():
                        forced_start_node = nodes[0]
                        break
        if forced_start_node:
            print(f"Anchoring routes at {secondary.get(forced_start_node)} ({forced_start_node})")
        else:
            print(f"Warning: couldn't find start station '{requested_start}'; ignoring.")

    # randomized trials parameters
    trials = max(1, int(getattr(args, "trials", 1)))
    noise = float(getattr(args, "noise", 0.05))
    seed = getattr(args, "seed", None)

    # parse explicit start arg (but do NOT commit to start_dt yet, we may compute per-trial)
    start_arg = getattr(args, "start", None)
    parsed_start_dt = None
    if start_arg:
        for fmt in ("%Y-%m-%d %H:%M", "%H:%M"):
            try:
                parsed = datetime.strptime(start_arg, fmt)
                if fmt == "%H:%M":
                    parsed_start_dt = datetime.combine(date.today(), parsed.time())
                else:
                    parsed_start_dt = parsed
                break
            except Exception:
                continue
        if parsed_start_dt is None:
            print("Couldn't parse --start; ignored (first departure after 04:00 will be used)")

    rng_master = random.Random(seed)
    # allow direct replay of a previously-recorded trial RNG seed
    replay_seed = getattr(args, "replay_trial_seed", None)
    # If user asked to replay a specific trial seed, force a single trial
    if replay_seed is not None and trials > 1:
        trials = 1
    top_k = int(getattr(args, "top_k", 3))
    two_opt_iters = int(getattr(args, "two_opt_iters", 200))
    no_two_opt = getattr(args, "no_two_opt", False)

    # Endless-mode options
    endless_mode = getattr(args, "endless", False)
    endless_threshold_str = getattr(args, "endless_threshold", None)
    if endless_threshold_str:
        try:
            if ":" in endless_threshold_str:
                h, m = map(int, endless_threshold_str.split(":"))
                endless_threshold_minutes = h * 60 + m
            else:
                endless_threshold_minutes = int(endless_threshold_str)
        except Exception:
            endless_threshold_minutes = WORLD_RECORD_MINUTES
    else:
        endless_threshold_minutes = WORLD_RECORD_MINUTES
    max_endless_trials = int(getattr(args, "max_endless_trials", 100000))

    if replay_seed is not None and endless_mode:
        print("Warning: --replay-trial-seed is incompatible with --endless; ignoring --endless.")
        endless_mode = False

    if endless_mode and forced_start_node:
        print("Endless mode: ignoring --start-station; choosing random start per trial.")
        forced_start_node = None

    # If endless mode requested, override `trials` with a large capped value
    if endless_mode:
        trials = max_endless_trials

    candidates = []

    trial_date_arg = getattr(args, "trial_date", None)
    if trial_date_arg:
        try:
            base_trial_date = date.fromisoformat(trial_date_arg)
        except Exception:
            print("Couldn't parse --date; using today.")
            base_trial_date = date.today()
    else:
        base_trial_date = date.today()

    try:
        for t in range(trials):
            
            cutoff_dt = datetime.combine(base_trial_date, time(4, 0))

            # deterministic trial RNG — use replay seed if provided for exact reproduction
            if replay_seed is not None:
                trial_seed = int(replay_seed)
            else:
                trial_seed = rng_master.randint(0, 2**31 - 1)
            
            trial_rng = random.Random(trial_seed)
            perturb_rng = random.Random(trial_rng.randint(0, 2**31 - 1))
            routing_rng = random.Random(trial_rng.randint(0, 2**31 - 1))
            del trial_rng  # prevent accidental reuse

            # perturb graph weights for search only
            pert_graph = perturb_graph_weights(graph, noise, perturb_rng) if noise > 0 else graph

            # compute candidate route from perturbed graph
            candidate_route = simulate_grand_tour(
                pert_graph,
                secondary,
                start_node=forced_start_node,
                rng=routing_rng if not forced_start_node else None,
            )

            # determine start_dt for this candidate
            if parsed_start_dt and parsed_start_dt >= cutoff_dt:
                candidate_start_dt = parsed_start_dt
            else:
                start_node = candidate_route[0]
                start_line_name = LETTER_TO_LINE.get(start_node[0], "")
                tt_file = _find_timetable_file_for_line(start_line_name, timetables)
                if tt_file:
                    trips = timetables.get(tt_file, [])
                    from_name = secondary.get(start_node, None)
                    from_norm = _norm(from_name)
                    dep_dt, tripid = find_first_departure_from_station(trips, from_norm, cutoff_dt)
                    candidate_start_dt = dep_dt if dep_dt else cutoff_dt
                else:
                    candidate_start_dt = cutoff_dt

            # refine with two-opt (validated against timed objective)
            if not no_two_opt:
                try:
                    refined_route, refined_timed = two_opt(candidate_route, graph, secondary, timetables, candidate_start_dt, max_iters=two_opt_iters, rng=routing_rng)
                except Exception:
                    refined_route = candidate_route
                    refined_timed = compute_timed_route(candidate_route, graph, secondary, timetables, candidate_start_dt)

            total_min = total_minutes_from_timed(refined_timed)

            # Per-trial one-line summary when running in endless mode
            if endless_mode:
                trial_start_node = candidate_route[0] if candidate_route else None
                trial_start_name = secondary.get(trial_start_node, trial_start_node) if trial_start_node else 'N/A'
                if total_min is None:
                    time_str = 'N/A'
                else:
                    th = total_min // 60
                    tm = total_min % 60
                    time_str = f"{th}h {tm}m"
                
                if args.json:
                    print(json.dumps({
                        "station": trial_start_name,
                        "node": trial_start_node,
                        "total_minutes": total_min,
                        "time_str": time_str,
                        "seed": trial_seed,
                        "date": base_trial_date.isoformat(),
                    }, ensure_ascii=False), flush=True)
                else:
                    print(f"{trial_start_name} ({trial_start_node}) — {time_str} — seed={trial_seed} — date={base_trial_date.isoformat()}")

            if total_min is None:
                continue

            candidate = {
                "total_min": total_min,
                "route": refined_route,
                "timed": refined_timed,
                "start_dt": candidate_start_dt,
                "trial_seed": trial_seed,
                "noise": noise,
            }
            candidates.append(candidate)
            if best_endless_candidate is None or total_min < best_endless_candidate["total_min"]:
                best_endless_candidate = candidate

            # If in endless mode and threshold reached, stop early and use this candidate
            if endless_mode and total_min <= endless_threshold_minutes:
                success_candidate = candidate
                print(f"Endless mode: found candidate <= threshold ({time_str}) at trial seed {trial_seed}")
                break
    except KeyboardInterrupt:
        print("Interrupted by user; processing candidates found so far...")

    if endless_mode and best_endless_candidate is not None:
        best_min = best_endless_candidate["total_min"]
        best_seed = best_endless_candidate["trial_seed"]
        bh = best_min // 60
        bm = best_min % 60
        print(f"\nBest endless result: {bh}h {bm}m — seed={best_seed} — date={base_trial_date.isoformat()}")

    if not candidates:
        print("No viable timed candidate found.")
        return

    # if an endless-mode success candidate was found, prefer it (print full tour)
    if 'success_candidate' in locals() and success_candidate is not None:
        best_candidate = success_candidate
    else:
        # sort and keep top-k best by timed total
        candidates.sort(key=lambda c: c["total_min"])  # ascending
        top_candidates = candidates[:top_k]
        best_candidate = top_candidates[0]

    # adopt best candidate
    route_reps = best_candidate["route"]
    timed = best_candidate["timed"]
    start_dt = best_candidate["start_dt"]
    # timed may include an expanded route (with intermediate nodes)
    expanded_route = timed.get("route", route_reps)
    depart_times = timed.get("depart_times", [])
    arrival_times = timed.get("arrival_times", [])
    edge_lines = timed.get("edge_lines", [])
    trip_ids = timed.get("trip_ids", [None] * max(0, len(depart_times)))

    # Build station-level route by taking the first occurrence of each station
    unique_indices = []
    seen = set()
    for idx, node in enumerate(expanded_route):
        station = secondary.get(node, node)
        if station not in seen:
            seen.add(station)
            unique_indices.append(idx)
    station_route = [expanded_route[i] for i in unique_indices]

    print("\nGrand Tour Route:")
    start_name = secondary.get(station_route[0], "Unknown Station")
    start_line = LETTER_TO_LINE.get(station_route[0][0], "Unknown Line")
    first_dep = None
    if unique_indices and unique_indices[0] < len(depart_times):
        first_dep = depart_times[unique_indices[0]]
    print(f"\nStart at {start_name} ({start_line}) — planned {start_dt.strftime('%Y-%m-%d %H:%M')}")
    if first_dep:
        print(f"  First departure at {first_dep.strftime('%H:%M')}")

    stations = -1
    saved_depart = None
    for s_idx in range(1, len(station_route) - 1):
        curr_station = station_route[s_idx]
        next_station = station_route[s_idx + 1]
        prev_station = station_route[s_idx - 1]

        curr_line = LETTER_TO_LINE.get(curr_station[0], "Unknown Line")
        next_line = LETTER_TO_LINE.get(next_station[0], "Unknown Line")

        is_transfer = curr_line != next_line
        is_uturn = prev_station == next_station
        stations += 1
        if is_transfer or is_uturn:
            curr_name = secondary.get(curr_station, "Unknown Station")
            next_name = secondary.get(next_station, "Unknown Station")
            # use expanded indices to look up timings and edge data
            curr_exp_idx = unique_indices[s_idx]
            next_exp_idx = unique_indices[s_idx + 1]
            edge = graph.get_edge_data(curr_station, next_station)
            transfer_line = edge.get("color", None) if edge else None

            # Only use transfer_line if it's a known line, otherwise use next_line
            if transfer_line in LINE_COLORS:
                line_label = transfer_line
                is_side_transfer = True
            else:
                line_label = next_line
                is_side_transfer = False

            arrive_time = arrival_times[curr_exp_idx] if curr_exp_idx < len(arrival_times) else None
            depart_next = depart_times[curr_exp_idx] if curr_exp_idx < len(depart_times) else None

            # compute ride time from the last boarding (start of continuous same-line run)
            ride_str = ""
            if arrive_time and curr_exp_idx - 1 >= 0:
                board_depart = get_board_departure_time(
                    curr_exp_idx - 1, edge_lines, trip_ids, depart_times, arrival_times
                )

                if args.verbose and board_depart:
                    def _fmt(dt):
                        return dt.strftime('%H:%M') if dt else 'N/A'
                    bi_log = curr_exp_idx - 1
                    start_slice = max(0, bi_log - 3)
                    end_slice = min(len(edge_lines), bi_log + 3)
                    print(f"DEBUG-SUM s_idx={s_idx} curr={curr_name} next={next_name} "
                          f"board_depart={_fmt(board_depart)} arrive_time={_fmt(arrive_time)} "
                          f"depart_next={_fmt(depart_next)}")
                    print("  edge_lines nearby:", edge_lines[start_slice:end_slice])
                    print("  depart_times nearby:", [_fmt(t) for t in depart_times[start_slice:end_slice]])
                    print("  arrival_times nearby:", [_fmt(t) for t in arrival_times[start_slice:end_slice+1]])

                if board_depart:
                    ride_delta = arrive_time - board_depart
                    # BUG FIX: removed the `saved_depart` override — it produced
                    # negative deltas because saved_depart < arrive_time
                    ride_minutes = int(ride_delta.total_seconds() / 60)
                    if ride_minutes < 0:
                        ride_minutes = 0
                    if ride_minutes >= 60:
                        ride_hours = ride_minutes // 60
                        ride_mins = ride_minutes % 60
                        ride_desc = f"{ride_hours}h {ride_mins}m"
                    else:
                        ride_desc = f"{ride_minutes}m"
                    ride_str = f" (ride time {ride_desc})"

            # build two variants of the action message
            if stations == 0:
                action_msg_long = f"Go back to {line_label} Line at {next_name} after visiting {curr_name} ({curr_line})"
                action_msg_short = f"Go back to {line_label} Line at {next_name}"
            elif is_uturn:
                action_msg_long = f"U-turn at {curr_name} ({curr_line}) after {stations} station{ 's' if stations > 1 else ''}"
                action_msg_short = f"U-turn after {stations} station{ 's' if stations > 1 else ''}"
            else:
                if curr_name == next_name:
                    action_msg_long = f"Transfer to {line_label} Line at {curr_name} after {stations} station{ 's' if stations > 1 else ''}"
                    action_msg_short = f"Transfer to {line_label} Line after {stations} station{ 's' if stations > 1 else ''}"
                elif is_side_transfer:
                    action_msg_long = f"Transfer at {curr_name} ({curr_line}) to {line_label} Line to get to {next_name} ({next_line})"
                    action_msg_short = f"Transfer to {line_label} Line to get to {next_name} ({next_line})"
                else:
                    action_msg_long = f"Transfer at {curr_name} ({curr_line}) to {line_label} Line at {next_name} after passing through {stations} station{ 's' if stations > 1 else ''}"
                    action_msg_short = f"Transfer to {line_label} Line at {next_name} after passing through {stations} station{ 's' if stations > 1 else ''}"

            if arrive_time:
                prefix = f"Arrive at {curr_name} ({curr_line}) at {arrive_time.strftime('%H:%M')}{ride_str}"
                msg = f"{prefix}, {action_msg_short}"
            else:
                msg = action_msg_long

            if depart_next:
                msg += f", depart {depart_next.strftime('%H:%M')}"
                saved_depart = depart_next

            print(msg)
            stations = -1

    end_name = secondary.get(station_route[-1], "Unknown Station")
    end_line = LETTER_TO_LINE.get(station_route[-1][0], "Unknown Line")
    final_arrival = arrival_times[unique_indices[-1]] if unique_indices and unique_indices[-1] < len(arrival_times) else None
    if final_arrival:
        print(f"End at {end_name} ({end_line}) — arrive {final_arrival.strftime('%Y-%m-%d %H:%M')}")
    else:
        print(f"End at {end_name} ({end_line})")

    # total overall time
    start_of_trip = None
    if depart_times and depart_times[0]:
        start_of_trip = depart_times[0]
    else:
        start_of_trip = arrival_times[0]
    if start_of_trip and final_arrival:
        total_delta = final_arrival - start_of_trip
        total_minutes = int(total_delta.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        print(f"Total tour time: {hours}h {minutes}m")

    # diagnostic waits
    if getattr(args, "debug_waits", False):
        threshold = getattr(args, "wait_threshold", 60)
        print(f"\nDiagnostics: waits >= {threshold} minutes:")
        problematic = []
        for i in range(len(depart_times)):
            arr = arrival_times[i]
            dep = depart_times[i]
            if not arr or not dep:
                continue
            wait_min = (dep - arr).total_seconds() / 60.0
            if wait_min >= threshold:
                u = expanded_route[i]
                v = expanded_route[i + 1]
                curr_name = secondary.get(u, "Unknown Station")
                next_name = secondary.get(v, "Unknown Station")
                line = edge_lines[i]
                tid = trip_ids[i]
                print(f"- Leg {i}: {u}->{v} ({curr_name} -> {next_name}) line={line} trip={tid} arr={arr.strftime('%Y-%m-%d %H:%M')} dep={dep.strftime('%Y-%m-%d %H:%M')} wait={int(wait_min)}m")
                problematic.append((i, wait_min, line))
        if problematic:
            bus_involved = any(p[2] == "Bus" for p in problematic)
            if bus_involved:
                print("Suggestion: bus connector appears in problematic legs. Try rerunning with --no-bus to disable the bus connector.")

    # verbose per-leg timings for diagnosis
    if getattr(args, "verbose", False):
        print("\nDetailed leg timings:")
        def fmt(dt):
            return dt.strftime('%Y-%m-%d %H:%M') if dt else 'N/A'
        for i in range(len(depart_times)):
            u = expanded_route[i]
            v = expanded_route[i + 1]
            line = edge_lines[i] or 'Unknown'
            tid = trip_ids[i] or 'N/A'
            arr_u = arrival_times[i]
            dep = depart_times[i]
            arr_v = arrival_times[i + 1]
            wait_min = 'N/A'
            if dep and arr_u:
                wait_min = f"{(dep - arr_u).total_seconds()/60.0:.1f}m"
            ride_min = 'N/A'
            # compute ride time from the boarding point for this arrival (start of continuous same-line run)
            if arr_v:
                board_depart = get_board_departure_time(
                    i, edge_lines, trip_ids, depart_times, arrival_times
                )

                # debug output for known problem stations (verbose leg)
                curr_name_v = secondary.get(u, 'Unknown Station')
                next_name_v = secondary.get(v, 'Unknown Station')
                if board_depart:
                    debug_stations = {"Sugamo", "Komagome", "Akabane-iwabuchi"}
                    if curr_name_v in debug_stations or next_name_v in debug_stations:
                        print(f"DEBUG-VERB leg={i} u={u}->{v} curr={curr_name_v} next={next_name_v} board_depart={fmt(board_depart)} arr_v={fmt(arr_v)} dep={fmt(dep)}")
                        bi = 0  # board_idx no longer available; slices are informational only
                        start_slice = max(0, bi - 3)
                        end_slice = min(len(edge_lines), bi + 3)
                        print("  edge_lines nearby:", edge_lines[start_slice:end_slice])
                        print("  depart_times nearby:", [fmt(t) for t in depart_times[start_slice:end_slice]])
                        print("  arrival_times nearby:", [fmt(t) for t in arrival_times[start_slice:end_slice+1]])
                        print("  trip_ids nearby:", [tid if tid else 'N/A' for tid in trip_ids[start_slice:end_slice]])
                ride_min = f"{int((arr_v - board_depart).total_seconds()/60)}m"
            print(f"Leg {i}: {u}->{v} | line={line} | trip={tid} | arr_at_{u}={fmt(arr_u)} | dep={fmt(dep)} | arr={fmt(arr_v)} | wait={wait_min} | ride={ride_min}")

    # Print reproduction info and target time to beat
    repro_seed = best_candidate.get("trial_seed") if best_candidate else None
    if repro_seed is not None:
        print(f"\nRepro Trial Seed: {repro_seed}")
        if seed is not None:
            print(f"Master Seed: {seed}")
        print(f"To reproduce this run exactly: python programs/tube_challenge.py --replay-trial-seed {repro_seed} --date {base_trial_date.isoformat()}")
    print(f"\nWorld Record: {format_timedelta_hms(WORLD_RECORD_DELTA)}")
    
    # Save last route data for external inspection (JSON)
    try:
        out_route_path = os.path.join("datasets", "last_route.json")
        out_data = {
            "expanded_route": expanded_route,
            "station_route": station_route,
            "depart_times": [dt.isoformat() if dt else None for dt in depart_times],
            "arrival_times": [dt.isoformat() if dt else None for dt in arrival_times],
            "edge_lines": edge_lines,
            "trip_ids": trip_ids,
            "start_dt": start_dt.isoformat() if isinstance(start_dt, datetime) else str(start_dt),
            "start_name": start_name,
            "end_name": end_name,
        }
        with open(out_route_path, "w") as _f:
            json.dump(out_data, _f, indent=2)
    except Exception:
        pass

    if getattr(args, "display_visualization", True):
        visualize_route(graph, expanded_route, positions)



def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Tokyo Metro Route Finder")

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed path steps for debugging",
    )
    parser.add_argument(
        "-S",
        "--start",
        dest="start",
        type=str,
        help="Start time in 'HH:MM' or 'YYYY-MM-DD HH:MM' format",
    )
    parser.add_argument(
        "--trials",
        type=int,
        dest="trials",
        default=10,
        help="Number of randomized trials to run (default 10)",
    )
    parser.add_argument(
        "--noise",
        type=float,
        dest="noise",
        default=0.15,
        help="Perturbation fraction for edge weights (e.g. 0.15 = +-15%%)",
    )
    parser.add_argument(
        "--master-seed",
        "--seed",
        type=int,
        dest="seed",
        default=None,
        help="Random master RNG seed for reproducible trials (alias: --seed)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        dest="top_k",
        default=3,
        help="Keep top-K candidate routes (default 3)",
    )
    parser.add_argument(
        "--two-opt-iters",
        type=int,
        dest="two_opt_iters",
        default=200,
        help="Max iterations for two-opt local search (default 200)",
    )
    parser.add_argument(
        "--no-two-opt",
        action="store_true",
        dest="no_two_opt",
        help="Disable two-opt refinement",
    )
    parser.add_argument(
        "--no-bus",
        action="store_true",
        dest="no_bus",
        help="Disable the custom bus connector between Y02 and E38",
    )
    parser.add_argument(
        "--debug-waits",
        action="store_true",
        dest="debug_waits",
        help="Print waits longer than the threshold for diagnosis",
    )
    parser.add_argument(
        "--wait-threshold",
        type=int,
        dest="wait_threshold",
        default=60,
        help="Minutes threshold for --debug-waits (default 60)",
    )
    parser.add_argument(
        "--start-station",
        dest="start_station",
        type=str,
        help="Start station name or node code (e.g. Zoshigaya or Z03)",
    )
    parser.add_argument(
        "--display-visualization",
        action="store_true",
        dest="display_visualization",
        help="Display the route visualization image after generation",
    )
    parser.add_argument(
        "--replay-trial-seed",
        dest="replay_trial_seed",
        type=int,
        default=None,
        help="Use this trial RNG seed to reproduce a specific trial exactly",
    )
    parser.add_argument(
        "--endless",
        action="store_true",
        dest="endless",
        help="Run trials until a candidate meets the threshold (default world record)",
    )
    parser.add_argument(
        "--endless-threshold",
        dest="endless_threshold",
        type=str,
        default=None,
        help="Stopping threshold (format 'HH:MM' or minutes). Default is world record",
    )
    parser.add_argument(
        "--max-endless-trials",
        dest="max_endless_trials",
        type=int,
        default=100000,
        help="Safety cap for endless mode (default 100000)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json",
        help="Output results in JSON format (for endless mode)",
    )
    parser.add_argument(
        "--date",
        dest="trial_date",
        type=str,
        default=None,
        help="Date for timetable lookups in YYYY-MM-DD format (default: today)",
    )
    return parser.parse_args()


def entry():
    """This is for running the script once deployed via brew"""
    try:
        args = parse_args()  # Parse the arguments here
        main(args)
    except KeyboardInterrupt:
        print("Exiting...")


if __name__ == "__main__":
    """This is for running the script during development"""
    entry()
