from itertools import islice

def k_shortest_paths(G, source, target, k, weight=None):
    return list(islice(nx.shortest_simple_paths(G, source, target,
                                                weight=weight), k))
