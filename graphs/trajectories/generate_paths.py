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
        paths_graph.add_edge("r{}c{}".format(row1+1, col1+1), "r{}c{}".format(row2+1, col2+1))
    nx.write_gml(paths_graph, "paths.gml")

