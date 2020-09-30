from networkx import nx
from itertools import islice

def k_shortest_paths(G, source, target, k, weight=None):
    return list(islice(nx.shortest_simple_paths(G, source, target,
                                                weight=weight), k))

def k_reasonable_paths(G, source, target, k, weight=None):
    src_neighs = G[source]
    paths = []

    for src_neigh in src_neighs:
        try:
            for k_path in k_shortest_paths(G,src_neigh,target,k,weight):
                paths.append([source] + k_path)
        except nx.NetworkXNoPath:
            continue
        
    return paths


