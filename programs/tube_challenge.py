import argparse
import json

import matplotlib.pyplot as plt
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
    "Unknown": "#cccccc",
}


def visualize_route(graph, route, positions):
    plt.figure(figsize=(16, 12))

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
        edge_colors.append(LINE_COLORS.get(line, "#cccccc"))

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
    plt.show()


def simulate_grand_tour(graph, secondary):
    """
    Simulate a grand tour of the Tokyo Metro starting from a given station.
    :param graph: The metro graph.
    :param start_station: The starting station code.
    :return: A list of stations in the tour.
    """
    unique_nodes = get_unique_station_nodes(graph, secondary)
    route = traveling_salesman_problem(
        graph, cycle=False, weight="weight", nodes=unique_nodes
    )
    return route


def add_custom_connections(graph):
    # Chuo Line between Nakano and Ogikubo - one transfer plus 2 stations
    graph.add_edge("T01", "M01", real_distance=4.5, weight=8.5, color="JR")

    # Chuo Sobu Line between Nishi-Funabashi and Motoyawata - one transfer plus one extra station
    graph.add_edge("T23", "S21", real_distance=3.4, weight=6.4, color="JR")

    # Keiyo Line between Shin-Kiba and Hatchobori - two connections so plus 4
    graph.add_edge("Y24", "H12", real_distance=13.3, weight=17.3, color="Rinkai")

    # Bus between Narimasu and Hikarigaoka - one transfer plus 9 stops
    graph.add_edge("Y02", "E38", real_distance=2.4, weight=4.4, color="Bus")

    # Seibu Yurakucho Line between Kotake-mukaihara and Nerima - one transfer plus 2 stops
    graph.add_edge("Y01", "F01", real_distance=2.5, weight=6.5, color="Seibu")

    # Yamanote Junctions (needs double checking)

    # Yamanote Line between Ikebukuro and Takadanobaba - one transfer plus 2 stops
    graph.add_edge("Y09", "T03", real_distance=2.0, weight=4.0, color="JR")
    # Yamanote Line between Takadanobaba and Shinjuku - one transfer plus 2 stops
    graph.add_edge("T03", "M08", real_distance=1.8, weight=3.8, color="JR")
    # Yamanote Line between Shinjuku and Yoyogi - one transfer plus 1 stops
    graph.add_edge("M08", "E26", real_distance=1.2, weight=2.2, color="JR")
    # Yamanote Line between Yoyogi and Shibuya - one transfer plus 1 stops
    graph.add_edge("E26", "G01", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Shibuya and Ebisu - one transfer plus 1 stops
    graph.add_edge("G01", "H02", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Ebisu and Meguro - one transfer plus 1 stops
    graph.add_edge("H02", "N01", real_distance=1.2, weight=2.2, color="JR")
    # Yamanote Line between Meguro and Gotanda - one transfer plus 1 stops
    graph.add_edge("N01", "A05", real_distance=1.5, weight=2.5, color="JR")
    # Yamanote Line between Shinbashi and Yurakucho - one transfer plus 1 stops
    graph.add_edge("A10", "Y18", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Yurakucho and Tokyo - one transfer plus 1 stops
    graph.add_edge("Y18", "M17", real_distance=1.2, weight=2.2, color="JR")
    # Yamanote Line between Tokyo and Kanda - one transfer plus 1 stops
    graph.add_edge("M17", "G13", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Kanda and Akihabara - one transfer plus 1 stops
    graph.add_edge("G13", "H16", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Akihabara and Ueno - one transfer plus 1 stops
    graph.add_edge("H16", "H18", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Ueno and Nishi-Nippori - one transfer plus 1 stops
    graph.add_edge("H18", "C16", real_distance=1.0, weight=2.0, color="JR")

    # Yamanote Line between Komagome and Sugamo - one transfer plus 1 stops
    graph.add_edge("N14", "I15", real_distance=1.0, weight=2.0, color="JR")
    # Yamanote Line between Sugamo and Ikebukuro - one transfer plus 1 stops
    graph.add_edge("I15", "M25", real_distance=1.0, weight=2.0, color="JR")

    return graph


def load_graph(verbose=False):
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
    graph = add_custom_connections(graph)

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
        graph = load_graph(args.verbose)
    except Exception as e:
        print("Error loading graph:", e)
        return

    route = simulate_grand_tour(graph, secondary)

    print("\nGrand Tour Route:")

    start_name = secondary.get(route[0], "Unknown Station")
    start_line = LETTER_TO_LINE.get(route[0][0], "Unknown Line")
    print(f"\nStart at {start_name} ({start_line})")
    stations = -1
    for idx in range(1, len(route) - 1):
        curr_station = route[idx]
        next_station = route[idx + 1]
        prev_station = route[idx - 1]

        curr_line = LETTER_TO_LINE.get(curr_station[0], "Unknown Line")
        next_line = LETTER_TO_LINE.get(next_station[0], "Unknown Line")

        is_transfer = curr_line != next_line
        is_uturn = prev_station == next_station
        stations += 1
        if is_transfer or is_uturn:
            curr_name = secondary.get(curr_station, "Unknown Station")
            next_name = secondary.get(next_station, "Unknown Station")
            edge = graph.get_edge_data(curr_station, next_station)
            transfer_line = edge.get("color", None) if edge else None

            # Only use transfer_line if it's a known line, otherwise use next_line
            if transfer_line in LINE_COLORS:
                line_label = transfer_line
                is_side_transfer = True
            else:
                line_label = next_line
                is_side_transfer = False

            if stations == 0:
                print(
                    f"Go back to {line_label} Line at {next_name} after visiting {curr_name} ({curr_line})"
                )
            elif is_uturn:
                print(
                    f"U-turn at {curr_name} ({curr_line}) after {stations} station{ 's' if stations > 1 else ''}"
                )
            else:
                if curr_name == next_name:
                    print(
                        f"Transfer to {line_label} Line at {curr_name} after {stations} station{ 's' if stations > 1 else ''}"
                    )
                elif is_side_transfer:
                    print(
                        f"Transfer at {curr_name} ({curr_line}) to {line_label} Line to get to {next_name} ({next_line})"
                    )
                else:
                    print(
                        f"Transfer at {curr_name} ({curr_line}) to {line_label} Line at {next_name} after passing through {stations} station{ 's' if stations > 1 else ''}"
                    )
            stations = -1

    end_name = secondary.get(route[-1], "Unknown Station")
    end_line = LETTER_TO_LINE.get(route[-1][0], "Unknown Line")
    print(f"End at {end_name} ({end_line})")

    visualize_route(graph, route, positions)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Tokyo Metro Route Finder")

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed path steps for debugging",
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
