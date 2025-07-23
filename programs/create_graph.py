import json

import matplotlib.pyplot as plt
import networkx as nx

with open("datasets/clean_stations.json") as f:
    data = json.load(f)

graph = nx.Graph()

# implement all translation maps
FILE_PATH = "datasets/secondary.json"
with open(FILE_PATH, "r") as file:
    secondary = json.load(file)
tertiary = dict((v, k) for k, v in secondary.items())
color_maps = {
    "BASE": "0.5",
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

for node, neighbors in data.items():
    # Assign line-specific color based on the first character of the node name
    line_code = node[0]
    node_color = color_maps.get(line_code, color_maps["BASE"])
    graph.add_node(node, color=node_color)
    for neighbor, weight in neighbors.items():
        # If this is a transfer edge (neighbor is same station, different line)
        if (
            secondary[node] == secondary[neighbor] and node[0] != neighbor[0]
        ) or weight <= 0:
            graph.add_edge(
                node,
                neighbor,
                weight=2.0,  # Algorithm weight (expensive to discourage zig-zagging)
                real_distance=weight,
                color=color_maps["BASE"],
            )
        else:
            edge_color = color_maps.get(line_code, color_maps["BASE"])
            graph.add_edge(
                node, neighbor, weight=weight, real_distance=weight, color=edge_color
            )

nx.write_graphml(graph, "datasets/tokyometro.graphml")


pos = nx.spring_layout(graph)
nx.draw(graph, pos, with_labels=True)
edge_labels = nx.get_edge_attributes(graph, "weight")
nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels)
plt.show()
