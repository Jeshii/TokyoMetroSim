import argparse
import json

import networkx as nx
from networkx.algorithms.approximation import traveling_salesman_problem

# implement all translation maps
FILE_PATH = "datasets/secondary.json"
with open(FILE_PATH, "r") as file:
    secondary = json.load(file)
tertiary = dict((v, k) for k, v in secondary.items())
letter_to_line = {
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


def simulate_grand_tour(graph):
    """
    Simulate a grand tour of the Tokyo Metro starting from a given station.
    :param graph: The metro graph.
    :param start_station: The starting station code.
    :return: A list of stations in the tour.
    """
    # Get all station nodes
    all_nodes = list(graph.nodes())
    # Use TSP to visit all stations, starting from start_station
    route = traveling_salesman_problem(
        graph, cycle=False, weight="weight", nodes=all_nodes
    )
    return route


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
    return graph


def main(args):

    # load metro #
    try:
        graph = load_graph(args.verbose)
    except Exception as e:
        print("Error loading graph:", e)
        return

    route = simulate_grand_tour(graph)

    for station in route:
        station_name = secondary.get(station, "Unknown Station")
        line_name = letter_to_line.get(station[0], "Unknown Line")
        print(f"{station_name} ({line_name})")


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
