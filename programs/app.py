import argparse
import json

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
    "A": "Rose",
    "I": "Blue",
    "S": "Leaf",
    "E": "Magenta",
    "G": "Orange",
    "M": "Red",
    "H": "Silver",
    "T": "Sky",
    "C": "Green",
    "Y": "Gold",
    "Z": "Purple",
    "N": "Emerald",
    "F": "Brown",
}


def get_route(start, end) -> str:
    # get route #
    dji = dijkstra(graph, tertiary[start], tertiary[end])

    # get output path #
    output = ""
    for i in range(len(dji[1]) - 1):
        if i == 0:
            output += "Board at " + secondary[dji[1][i]] + " Station\n"
        if i == len(dji[1]) - 2:
            output += (
                "Ride on the "
                + letter_to_line[dji[1][i][0]]
                + " line until "
                + secondary[dji[1][i + 1]]
                + " Station\n"
            )
        if dji[1][i + 1][0] == dji[1][i][0]:
            continue
        output += (
            "Ride on the "
            + letter_to_line[dji[1][i][0]]
            + " line until "
            + secondary[dji[1][i]]
            + " Station\n"
        )
    output += "Total distance traveled: " + str(round(dji[0], 2)) + " km\n"

    return output


def main(args):

    args.start = inquirer.fuzzy(
        message="Departure: ", choices=tertiary.keys()
    ).execute()
    args.end = inquirer.fuzzy(
        message="Destination: ", choices=tertiary.keys()
    ).execute()

    ROUTE = get_route(args.start, args.end)

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
