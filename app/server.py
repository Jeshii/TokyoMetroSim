# ----------------- imports ----------------- #
import algorithm
import map_visualizer
import networkx as nx  # graph

# ----------------- routes ----------------- #


def get_path(source, destination):
    # load graph #
    metro_graph = nx.read_graphml("../datasets/tokyometro.graphml")

    # find path #
    distance, path, path_string = algorithm.path_find(metro_graph, source, destination)

    # get visualization #
    graph = map_visualizer.visualize_path(path)
    response = {
        "distance": distance,
        "path": path,
        "path_string": path_string,
        "graph": graph,
    }
    return response
    # user output #
