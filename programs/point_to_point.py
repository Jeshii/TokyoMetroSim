import argparse
import json
import random

import networkx as nx
from dijkstras import dijkstra
from InquirerPy import inquirer

# load metro #
graph = nx.read_graphml("datasets/tokyometro.graphml")

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


def get_route(start: str, end: str, verbose: bool = False) -> str:
    """
    Get the route from start to end using Dijkstra's algorithm.
    :param start: Starting station code.
    :param end: Ending station code.
    :param verbose: If True, print detailed path steps.
    :return: Formatted string of the route.
    """
    dji = dijkstra(graph, tertiary[start], tertiary[end])

    if verbose:
        print("Raw path from dijkstra:")
        for idx in range(len(dji[1]) - 1):
            node = dji[1][idx]
            next_node = dji[1][idx + 1]
            line = letter_to_line.get(node[0], "Unknown")
            station = secondary.get(node, "Unknown")
            edge_weight = graph.get_edge_data(node, next_node)["weight"]
            print(
                f"  {node} -> {next_node}: {station} ({line} line), weight={edge_weight}"
            )

    output = ""
    # Check if the first two nodes are a transfer at the start
    if len(dji[1]) > 1 and secondary[dji[1][0]] == secondary[dji[1][1]]:
        output += (
            "Board the "
            + letter_to_line[dji[1][1][0]]
            + " line at "
            + secondary[dji[1][1]]
            + " Station\n"
        )
        start_index = 1
    else:
        output += (
            "Board the "
            + letter_to_line[dji[1][0][0]]
            + " line at "
            + secondary[dji[1][0]]
            + " Station\n"
        )
        start_index = 0

    for i in range(start_index, len(dji[1]) - 1):
        if dji[1][i + 1][0] != dji[1][i][0]:
            output += (
                "Transfer to the "
                + letter_to_line[dji[1][i + 1][0]]
                + " line at "
                + secondary[dji[1][i + 1]]
                + " Station\n"
            )
    output += "Arrive at " + secondary[dji[1][-1]] + " Station\n"
    output += "Total distance traveled: " + str(round(dji[0], 2)) + " km\n"

    return output


def main(args):

    if not args.start:
        args.start = inquirer.fuzzy(
            message="Departure: ", choices=tertiary.keys()
        ).execute()
    elif args.start == "random":
        args.start = random.choice(list(tertiary.keys()))
    elif args.start not in tertiary:
        print(f"Invalid starting station: {args.start}")
        return

    if not args.end:
        args.end = inquirer.fuzzy(
            message="Destination: ", choices=tertiary.keys()
        ).execute()
    elif args.end == "random":
        args.end = random.choice(list(tertiary.keys()))
    elif args.end not in tertiary:
        print(f"Invalid ending station: {args.end}")
        return

    ROUTE = get_route(args.start, args.end, args.verbose)

    print("\n" + ROUTE + "\n")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Tokyo Metro Route Finder")
    parser.add_argument(
        "--start",
        type=str,
        help="Starting station (e.g., 'Wakoshi')",
    )
    parser.add_argument(
        "--end",
        type=str,
        help="Ending station (e.g., 'Nishi-magome')",
    )
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
