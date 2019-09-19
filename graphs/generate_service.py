import networkx as nx
import random
import sys
import logging
from rainbow_logging_handler import RainbowLoggingHandler


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

        # =====================  attribute strings =================== #
        self.infra_node_capacity_str = 'cpu'
        self.infra_fixed_cost_str = 'fixed_cost'
        self.infra_unit_cost_str = 'unit_cost'
        self.endpoint_type_str = 'endpoint'
        self.type_str = 'type'
        self.server_type_str = 'server'
        self.access_point_type_str = 'cell'
        self.fog_nodes_type_str = 'fogNode'
        # TODO: These might have multiple types, just like the switches and servers!
        self.access_point_strs = ['pico_cell', 'micro_cell', 'macro_cell']
        self.server_strs = ['m{}_server'.format(i) for i in range(1,4)]

        super(InfrastructureGMLGraph, self).__init__(incoming_graph_data, gml_file=gml_file, label=label, **attr)
        # NOTE: duplication of information storage should be avoided (do not store information in class attributes, which can de
        # directly accessed at the network x dicts of the class. Only create attributes, if if they need calculation based on the
        # input information in the GML file (i.e. mobility pattern)
        # TODO: calculate coverage probabilities from the created mobility pattern
        self.random = random.Random(seed)

        # store ID-s of all relevant node types 
        self.endpoint_ids = [v['name'] for _,v in self.nodes(data=True)\
                        if v[self.type_str] == self.endpoint_type_str]
        self.access_point_ids = [v['name'] for _,v in self.nodes(data=True)\
                        if v[self.type_str] == self.access_point_type_str]
        self.server_ids = [v['name'] for _,v in self.nodes(data=True)\
                        if v[self.type_str] in self.server_type_str]
        self.mobile_ids = [v['name'] for _,v in self.nodes(data=True)\
                        if v[self.type_str] == self.fog_nodes_type_str]
        for n, node_dict in self.nodes(data=True):
            # TODO: read or generate or set statically the costs of each nodes?
            node_dict[self.infra_fixed_cost_str] = self.random.uniform(0, 10)
            node_dict[self.infra_unit_cost_str] = self.random.uniform(1, 2)

            if node_dict[self.type_str] == self.endpoint_type_str:
                self.endpoint_ids.append(n)
            elif node_dict[self.type_str] in self.access_point_strs:
                self.access_point_ids.append(n)
            elif node_dict[self.type_str] in self.server_strs:
                self.server_ids.append(n)

    def check_graph(self):
        """
        # TODO: check if this format complies to the AMPL converter and the ConstructiveMapperFromFractional's desired format.

        :return:
        """
        return True


class ServiceGMLGraph(nx.DiGraph):

    def __init__(self, infra: InfrastructureGMLGraph, connected_component_sizes, sfc_delays, seed, series_parallel_ratio, incoming_graph_data=None, **attr):
        """
        Generates a service using series parallel graph structures with SFC-s on its paths on top of infra with parameters given.

        :param seed: randomization seed
        :param series_parallel_ratio:
        :param sfc_delays: list of delay values, which the chains can take
        :param infra:
        :param incoming_graph_data: If it is given, additional elements are created at the nx.DiGraph
        :param connected_component_sizes: list of integers describing the number and size of the connected service graph components
        :param attr:
        """
        # =====================  attribute strings =================== #
        self.nf_demand_str = 'weight'
        self.location_constr_str = 'location_constraints'   # list of node ids, where an NF may be mapped
        self.sfc_delays_list_str = 'sfc_delays'             # list of (delay, edge path) tuples containing chain delays.

        super(ServiceGMLGraph, self).__init__(incoming_graph_data=incoming_graph_data, **attr)
        self.connected_component_sizes = connected_component_sizes
        self.sfc_delays = sfc_delays
        self.infra = infra
        self.random = random.Random(seed)
        self.current_node_id = 0
        self.series_parallel_ratio = series_parallel_ratio
        self.log = logging.Logger('ServiceGMLGraph')
        handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
        formatter = logging.Formatter('%(asctime)s(%(name).6s)%(levelname).3s: %(message)s')
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG)
        self._generate_structure()
        self.vnfs= [v['name'] for _,v in self.nodes(data=True)]

    def generate_series_parallel_graph(self, n):
        """
        Creates SP graphs with this definition: http://www.graphclasses.org/classes/gc_275.html
        And adds the structure to this instance

        :param n:
        :return:
        """
        # at each call of this function we add a connected component to the overall SG
        # self.current_node_id += 1
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
            self.add_node(u, weight=self.random.uniform(35, 100))
        for u,v,k in G.edges:
            if u != v and not self.has_edge(u, v):
                # TODO: add parameters
                self.add_edge(u, v)

    def check_graph(self):
        """


        :return:
        """
        # TODO: use strings of the class about the input structure.
        return True

    def _add_service_function_loops(self):
        """


        :return:
        """
        # NOTE: this is nasty, if causes problems anywhere else, we can figure out a better way to call weakly_connected_component_subgraphs
        self.__class__ = nx.DiGraph
        cc = list(nx.weakly_connected_component_subgraphs(self))
        self.__class__ = ServiceGMLGraph
        for connected_subgraph in cc:
            try:
                loop = nx.find_cycle(connected_subgraph)
                # assign the first node in the loop as the endpoint of the circular chain
                endpoint_vnf_id = loop[0][0]
                endpoint_infra_id = self.random.choice(self.infra.endpoint_ids)
                self.nodes[endpoint_vnf_id][self.location_constr_str] = [endpoint_infra_id]
                # endpoints do not have resources
                self.nodes[endpoint_vnf_id][self.nf_demand_str] = 0

                # save chain latency info to .graph dict
                sfc_delay = self.random.choice(self.sfc_delays)
                self.graph[self.sfc_delays_list_str] = (sfc_delay, loop)
                self.log.debug("Adding SFC from VNF {} to endpoint {} with delay {} on path {}".
                               format(endpoint_vnf_id, endpoint_infra_id, sfc_delay, loop))
            except nx.NetworkXNoCycle:
                self.log.debug("No cycle found in component of size {}".format(connected_subgraph.number_of_nodes()))

    def _generate_structure(self):
        """
        Creates the overall structure of the service graph containing multiple connected components

        :return:
        """
        for n in self.connected_component_sizes:
            self.generate_series_parallel_graph(n)
        self._add_service_function_loops()
