import math
import networkx as nx


def get_internal_point(container, col, row):
    coords = {}
    for axis in ('lat', 'lon'):
        cumm_axis = 0.0
        for r, c, pos in ((0, 0, 'br'), (1, 0, 'tr'), (1, 1, 'tl'), (0, 1, 'bl')):
            label = "r{}c{}{}".format(row + r, col + c, pos)
            cumm_axis += container.nodes[label][axis]
        coords[axis] = cumm_axis / 4.0
    return coords


def get_distance(G, n1, n2):
    return math.sqrt((G.nodes[n1]['lon'] - G.nodes[n2]['lon'])**2 +
                     (G.nodes[n1]['lat'] - G.nodes[n2]['lat'])**2)


if __name__ == '__main__':
    container = nx.read_gml("containers.gml", destringizer=float)
    paths_graph = nx.Graph()
    for col in range(1, 6):
        for row in range(1, 10):
            base_label = "r{}c{}".format(row, col)
            if col == 1:
                type = 'start'
            elif col == 5:
                type = 'finish'
            else:
                type = 'path'
            paths_graph.add_node(base_label, **get_internal_point(container, col, row), type=type)
    for u, v in nx.grid_graph([5, 9]).edges():
        row1, col1 = u
        row2, col2 = v
        n1 = "r{}c{}".format(row1+1, col1+1)
        n2 = "r{}c{}".format(row2+1, col2+1)
        paths_graph.add_edge(n1, n2, distance=get_distance(paths_graph, n1, n2))
    nx.write_gml(paths_graph, "paths.gml")

