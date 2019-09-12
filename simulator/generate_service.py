import networkx as nx
import random


class GMLGraph(nx.DiGraph):

    def __init__(self, incoming_graph_data=None, gml_file=None, label='label', **attr):
        if gml_file is not None:
            super(GMLGraph, self).__init__(incoming_graph_data=nx.read_gml(gml_file, label=label))
        else:
            super(GMLGraph, self).__init__(incoming_graph_data, **attr)

    def check_graph(self):
        """
        Function to be overridden in a concrete subclass which represents a service or substrate.

        :return:
        """
        return True

    def serialize(self, file_path):
        nx.write_gml(self, file_path)


class InfrastructureGMLGraph(GMLGraph):

    def __init__(self, incoming_graph_data=None, gml_file=None, label='label', seed=0, **attr):
        super(InfrastructureGMLGraph, self).__init__(incoming_graph_data, gml_file=gml_file, label=label, **attr)
        # NOTE: duplication of information storage should be avoided (do not store information in class attributes, which can de
        # directly accessed at the network x dicts of the class. Only create attributes, if if they need calculation based on the
        # input information in the GML file (i.e. mobility pattern)
        # TODO: calculate coverage probabilities from the created mobility pattern
        self.random = random.Random(seed)
        for n, node_dict in self.nodes(data=True):
            node_dict['fixed_cost'] = self.random.uniform(0, 10)
            node_dict['unit_cost'] = self.random.uniform(1, 2)

    def check_graph(self):
        """
        # TODO: check if this format complies to the AMPL converter and the ConstructiveMapperFromFractional's desired format.

        :return:
        """
        return True


class ServiceGMLGraph(nx.DiGraph):

    def __init__(self, infra: InfrastructureGMLGraph, connected_component_sizes, seed, series_parallel_ratio, incoming_graph_data=None, **attr):
        """
        Generates a service using series parallel graph structures with SFC-s on its paths on top of infra with parameters given.

        :param seed: randomization seed
        :param series_parallel_ratio:
        :param infra:
        :param incoming_graph_data: If it is given, additional elements are created at the nx.DiGraph
        :param connected_component_sizes: list of integers describing the number and size of the connected service graph components
        :param attr:
        """
        super(ServiceGMLGraph, self).__init__(incoming_graph_data=incoming_graph_data, **attr)
        self.connected_component_sizes = connected_component_sizes
        self.infra = infra
        self.random = random.Random(seed)
        self.current_node_id = 1
        self.series_parallel_ratio = series_parallel_ratio
        self._generate_structure()

    def generate_series_parallel_graph(self, n):
        """
        Creates SP graphs with this definition: http://www.graphclasses.org/classes/gc_275.html
        And adds the structure to this instance

        :param n:
        :return:
        """
        G = nx.MultiDiGraph()
        G.add_node(self.current_node_id)
        G.add_edge(self.current_node_id, self.current_node_id)
        self.current_node_id += 1
        while G.number_of_nodes() < n:
            p = self.random.random()
            u, v = self.random.choice(list(G.edges()))
            if p < self.series_parallel_ratio:
                # subdivide an edge
                # deterministically remove always the smallest ID edge
                k = min(G[u][v].keys())
                G.remove_edge(u, v, k)
                G.add_node(self.current_node_id)
                G.add_edge(u, self.current_node_id)
                G.add_edge(self.current_node_id, v)
                self.current_node_id += 1
            else:
                # add parallel edge
                G.add_edge(u, v)
        for u in G.nodes:
            # TODO: add parameters
            self.add_node(u, weight=self.random.uniform(1, 10))
        for u,v,k in G.edges:
            if u != v and not self.has_edge(u, v):
                # TODO: add parameters
                self.add_edge(u, v)

    def check_graph(self):
        """


        :return:
        """
        return True

    def _generate_structure(self):
        for n in self.connected_component_sizes:
            self.generate_series_parallel_graph(n)
