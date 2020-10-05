from typing import Union, Generator
from networkx import nx
from itertools import islice

def k_shortest_paths(G, source, target, k, weight=None):
    """ Taken from
    https://networkx.github.io/documentation/networkx-1.10/reference/generated/networkx.algorithms.simple_paths.shortest_simple_paths.html
    """
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


def range_dfs(self, graph: nx.graph.Graph, start: Union[str,int],
        goal: Union[str,int], range_: Union[int,float],
        weight: str) -> Generator[list,None,None]:
    """Implementation of a Range-based DFS, based on
    https://eddmann.com/posts/depth-first-search-and-breadth-first-search-in-python/


    :graph: nx.graph.Graph: graph instance
    :start: Union[str,int]: starting node
    :goal: Union[str,int]: target node
    :range_: Union[int,float]: range of search
    :weight: str: weight to be used in the range

    :return: Generator[list]: [[start,a,...,goal], ...] with
                              sum(weight(start,a), ...) <= range_
    """
    stack = [(start, [start], 0)]
    while stack:
        (vertex, path, path_weight) = stack.pop()
        print(f'Evaluating path {path}')
        for next in set(graph[vertex]).difference(set(path)):
            total_weight = path_weight + graph[vertex][next][weight]

            if total_weight > range_:
                pass
            elif next == goal:
                yield path + [next]
            else:
                stack.append((next, path + [next], total_weight))

