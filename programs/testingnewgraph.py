# ----------- libraries import ----------- #
import json

import dijkstras
import matplotlib.pyplot as plt
import networkx as nx

# ----------- load files ----------- #
with open("../datasets/clean_stations.json") as f:
    data = json.load(f)

with open("../datasets/secondary.json", "r") as f:
    names = json.load(f)

graph = nx.Graph()
with open("../datasets/station_positions.json", "r") as f:
    positions = json.load(f)

BASE_COLOR = "0.0"

# When getting pixel coords, need to subtact y coord from 1785 (height of image) to get correct coords (otherwise flipped)
for i in positions:
    positions[i][1] = 1785 - positions[i][1]

for node, neighbors in data.items():
    graph.add_node(node, pos=(positions[node][0], positions[node][1]))
    for neighbor, weight in neighbors.items():
        graph.add_edge(node, neighbor, weight=weight)


# ----------- find path ----------- #
# get path #
# path = ["A01", "A02", "A03"]
path = dijkstras.dijkstra(graph, "A01", "S19")[1]


# convert to station names #
# load stations lookup
with open("../datasets/full_intersections.json", "r") as f:
    station_lookup = json.load(f)

# modify lookup to congregate names
station_lookup = {k: list(v.keys()) for k, v in station_lookup.items()}
# replace
path_expanded = []
previous_station = None
for station in path:
    # get associated stations
    station_name = names[station]
    if station_name == previous_station:
        continue

    try:
        intersecting_stations = station_lookup[station_name]
    except KeyError:
        continue
    previous_station = station_name

    # add
    path_expanded += intersecting_stations
# ----------- draw map ----------- #
# get attributes #
nodes = graph.nodes(data=True)
edges = graph.edges(data=True)
color_map_nodes = [BASE_COLOR] * len(nodes)
color_map_edges = [BASE_COLOR] * len(edges)

# labels
names_path = {
    key: value for key, value in names.items() if key in nodes and key in path
}

nodes_list = list(graph.nodes())
edges_list = list(graph.edges())
# node colors for only path
for node in path:
    color_map_nodes[nodes_list.index(node)] = positions[node][2]
    station_name = names_path[node]
    try:
        intersecting_stations = station_lookup[station_name]
    except KeyError:
        continue
    for station in intersecting_stations:
        color_map_nodes[nodes_list.index(station)] = positions[node][2]

# edge colors for only path
for start, end in zip(path, path[1:]):
    edge = (start, end)
    station_name1 = names[edge[0]]
    station_name2 = names[edge[1]]
    try:
        color_map_edges[edges_list.index(edge)] = color_map_nodes[
            nodes_list.index(edge[0])
        ]
    except ValueError:
        color_map_edges[edges_list.index((edge[1], edge[0]))] = color_map_nodes[
            nodes_list.index(edge[0])
        ]
    try:
        intersecting_stations1 = station_lookup[station_name1]
        intersecting_stations2 = station_lookup[station_name2]
    except KeyError:
        continue
    for station1 in intersecting_stations1:
        for station2 in intersecting_stations2:
            inter_edge = (station1, station2)
            if inter_edge in edges_list:
                color_map_edges[edges_list.index(inter_edge)] = color_map_nodes[
                    nodes_list.index(edge[0])
                ]

for i in path:
    station_name = names_path[i]
    try:
        intersecting_stations = station_lookup[station_name]
    except KeyError:
        continue
# positions
# pos = {node: attr["pos"] for node, attr in nodes}
pos = nx.get_node_attributes(graph, "pos")
print(path)

check = path[0][0]
print(check)
hold = []
hold.append(path[0])
for i in range(len(path)):
    if path[i][0] != check:
        hold.append(path[i])
        check = path[i][0]
if path[len(path) - 1] not in hold:
    hold.append(path[len(path) - 1])
print(hold)
node_label_dict = {}
for i in hold:
    node_label_dict[i] = dijkstras.secondary[i]
print(node_label_dict)
nx.set_node_attributes(graph, node_label_dict, "label")

# draw graph #
nx.draw_networkx(
    graph,
    pos=pos,
    node_size=50,
    labels=node_label_dict,
    node_color=color_map_nodes,
    edge_color=color_map_edges,
    with_labels=True,
    font_size=8,
)

plt.show()
