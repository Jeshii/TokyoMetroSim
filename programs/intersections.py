"""
This file defines the functionality for displaying any set of metro
stations given their longitude and latitude coordinates. To be run as a
script.
"""

import json

# import libraries #
import networkx as nx

# import * from dijkstras.py


# calculate coordinates #
# setup
BR_CORNER_COORD = (2526, 1785)  # using traditional pixel position as matrix
COORDS_PATH = "../datasets/station_positions.json"
STATIONS_PATH = "../datasets/secondary.json"
SCALE = 1

# execute setup
width = BR_CORNER_COORD[0]
height = BR_CORNER_COORD[1]

with open(COORDS_PATH, "r") as f:
    coords_dict = json.load(f)
with open(STATIONS_PATH, "r") as f:
    stations_dict = json.load(f)

# calculate positions
graph = nx.read_graphml("../datasets/tokyometro.graphml")
coords = dict()  # stores station name : position
for station_id, station_name in stations_dict.items():
    # force string match
    # station_name = station_name.title()

    # control for missing lines
    try:
        coords_dict[station_id]
    except Exception as e:
        print(f"Missing coordinates for {station_id}: {e}")
        continue

    # check already calculated
    if station_name in coords:
        # print mistakes
        if coords_dict[station_id][0:1] != list(coords[station_name].values())[0][0:1]:
            print(station_id, coords_dict[station_id])
            print(coords[station_name])

        # check neighbors
        if set(graph.neighbors(station_id)) != set(
            graph.neighbors(list(coords[station_name].keys())[0])
        ):
            print(station_name)
            print(
                set(graph.neighbors(station_id)),
                set(graph.neighbors(list(coords[station_name].keys())[0])),
            )

        # force correct mistakes
        coords[station_name][station_id] = list(coords[station_name].values())[0]
    else:
        # create new entry
        coords[station_name] = dict()
        coords[station_name][station_id] = coords_dict[station_id]

# convert back
combined_coords = dict()
for stations in coords.values():
    combined_coords.update(stations)


# save results #
with open("../datasets/corrected_intersections.json", "w") as f:
    json.dump(combined_coords, f, indent=4)
with open("../datasets/full_intersections.json", "w") as f:
    json.dump(coords, f, indent=4)
