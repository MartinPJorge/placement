import networkx as nx
import random
import math
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

    def get_connected_components(self):
        tmp_class_name = self.__class__
        self.__class__ = nx.DiGraph
        cc = list(nx.weakly_connected_component_subgraphs(self))
        self.__class__ = tmp_class_name
        return cc


class InfrastructureGMLGraph(GMLGraph):

    def __init__(self, incoming_graph_data=None, gml_file=None, label='label', seed=0, cluster_move_distances=None,
                 time_interval_count=None, **attr):
        """
        Reads a gml file constructed by mec-gen and generates the additional parameters.

        :param time_interval_count: how many time frames are simulated
        :param incoming_graph_data:
        :param gml_file:
        :param label:
        :param seed:
        :param cluster_move_distances: list of lengths of each cluster's line mobility pattern where the cluster goes there and back
                                       during the simulated time interval.
        :param attr:
        """

        # =====================  attribute strings =================== #
        self.time_interval_count = time_interval_count
        self.infra_node_capacity_str = 'cpu'
        self.infra_fixed_cost_str = 'fixed_cost'
        self.infra_unit_cost_str = 'unit_cost'
        self.endpoint_type_str = 'endpoint'
        self.type_str = 'type'
        self.server_type_str = 'server'
        self.access_point_type_str = 'cell'
        self.fog_nodes_type_str = 'fogNode'
        # the distance which the AP wireless connectivity reaches with high reliability
        self.ap_reach_str = 'reach'
        # used in self.ap_coverage_probabilities dictionary to name (as dict key) the mobile clusters
        self.mobile_cluster_prefix = 'mobile_cluster_'
        # TODO: These might have multiple types, just like the switches and servers!
        self.access_point_strs = ['pico_cell', 'micro_cell', 'macro_cell', 'cell']
        self.server_strs = ['m{}_server'.format(i) for i in range(1,4)]
        self.server_strs.append('server')
        self.mobile_node_str = 'fogNode'

        super(InfrastructureGMLGraph, self).__init__(incoming_graph_data, gml_file=gml_file, label=label, **attr)
        # NOTE: duplication of information storage should be avoided (do not store information in class attributes, which can de
        # directly accessed at the network x dicts of the class. Only create attributes, if if they need calculation based on the
        # input information in the GML file (i.e. mobility pattern)
        self.random = random.Random(seed)

        # store ID-s of all relevant node types
        # TODO: name is not much helpful for processing the data of the nodes, ID-s are used as keys in the networkx graph (see next for cycle)
        self.endpoint_ids, self.access_point_ids, self.server_ids, self.mobile_ids = [], [], [], []
        # self.endpoint_ids = [v['name'] for _,v in self.nodes(data=True)\
        #                 if v[self.type_str] == self.endpoint_type_str]
        # self.access_point_ids = [v['name'] for _,v in self.nodes(data=True)\
        #                 if v[self.type_str] == self.access_point_type_str]
        # self.server_ids = [v['name'] for _,v in self.nodes(data=True)\
        #                 if v[self.type_str] in self.server_type_str]
        # self.mobile_ids = [v['name'] for _,v in self.nodes(data=True)\
        #                 if v[self.type_str] == self.fog_nodes_type_str]
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
            elif node_dict[self.type_str] == self.mobile_node_str:
                self.mobile_ids.append(n)
        self.cluster_endpoint_ids = []
        # contains dictionary for each mobile cluster which is a dict of each time instance which is
        # a dict of each AP_id to their coverage probability.
        self.ap_coverage_probabilities = {}
        if cluster_move_distances is not None:
            self.generate_mobility_pattern(cluster_move_distances)

    def check_graph(self):
        """
        # TODO: check if this format complies to the AMPL converter and the ConstructiveMapperFromFractional's desired format.

        :return:
        """
        return True

    def generate_mobility_pattern(self, cluster_move_distances):
        """
        Calculates the coverage probabilities of each cluster in each time instance by each AP.
        A simple pattern is used: the cluster moves in a line distance specified in cluster_move_distances and moves back to the
        starting point by the end of the simulated time interval.

        :return:
        """
        for connected_comp in self.get_connected_components():
            # see if this is a mobile node cluster
            if any(m in connected_comp for m in self.mobile_ids):
                # there must be at least one endpoint in each cluster
                endpoint = filter(lambda m: m in self.endpoint_ids, connected_comp.nodes).__next__()
                self.cluster_endpoint_ids.append(endpoint)
                master_mobile = self.random.choice([filter(lambda m: m in self.mobile_ids, connected_comp.nodes)])
                mobile_cluster_id = self.mobile_cluster_prefix + str(master_mobile)
                move_distance = cluster_move_distances.pop()
                dist_in_one_interval = 2 * move_distance / float(self.time_interval_count)
                init_master_coordinates = (self.nodes[master_mobile]['lat'], self.nodes['lon'])
                best_move_vector = self.minimize_direction_of_move(init_master_coordinates, dist_in_one_interval)
                # e.g. direction_multiplier_list = [0, 1, 2, 3, 2, 1], where time_interval_count = 6 OR 7
                direction_multiplier_list = list(range(0, self.time_interval_count//2))
                direction_multiplier_list.extend(range(self.time_interval_count//2, 0, -1))
                if self.time_interval_count % 2 == 1:
                    # as a last step return to initial point in case of odd number of intervals
                    direction_multiplier_list.append(0)
                # shifts p in direction of v by d units
                push_point = lambda p, v, d: (p[0] + v[0]*d, p[1] + v[1]*d)
                time_intervald_indexes = list(reversed(list(range(1, self.time_interval_count+1))))
                for dir_mul in direction_multiplier_list:
                    current_p = push_point(init_master_coordinates, best_move_vector, dir_mul * dist_in_one_interval)
                    time_interval_idx = time_intervald_indexes.pop()
                    self.ap_coverage_probabilities[mobile_cluster_id] = {time_interval_idx: {}}
                    for ap_id in self.access_point_ids:
                        self.ap_coverage_probabilities[mobile_cluster_id][time_interval_idx][ap_id] = \
                            self.get_coverage_probability(current_p, ap_id)

    def get_coverage_probability(self, current_mobile_pos, ap_id):
        """
        Calculates the probabilty of covering the mobile node in its current position by the given AP.
        Uses the reach of the AP to get the probability. If the mobile position is on the border of the reach the
        probability drastically drops.

        :param current_mobile_pos:
        :param ap_id:
        :return:
        """
        Pjx, Pjy = self.relative_coordinates(current_mobile_pos, self.nodes[ap_id])
        dist = math.sqrt(Pjx ** 2 + Pjy ** 2)
        reach = self.nodes[ap_id][self.ap_reach_str]
        # TODO: get better model for coverage probability dropping based on research
        # drops to 0.0 probability somewhere after 20% beyond the reach of the AP, decreases squared from 1.0
        probability = 1.0
        raw_probability = - (dist / (reach * 1.2)) ** 2 + 1.1
        if raw_probability < 0.0:
            probability = 0.0
        elif raw_probability < 1.0:
            # use the values of the function between 0.0 and 1.0
            probability = raw_probability
        return probability

    def relative_coordinates(self, init_master_coordinates, ap_data):
        """
        Coordinates of AP in the system where init_master_coordinates is the origo

        :param init_master_coordinates:
        :param ap_data:
        :return:
        """
        return ap_data['lat'] - init_master_coordinates[0], ap_data['lon'] - init_master_coordinates[1]

    def relative_ap_coordinates(self, point):
        """
        Iterator on the coordinates of ALL APs in the system where point is the origo.

        :param point:
        :return:
        """
        for ap_id in self.access_point_ids:
            # convert AP coordinates to init_master_coordinates centered system
            Pjx, Pjy = self.relative_coordinates(point, self.nodes[ap_id])
            yield Pjx, Pjy

    def total_ap_distance_from_point(self, point):
        """
        Total distance of all APs from the input point.

        :param point:
        :return:
        """
        sum_dist = 0.0
        for Pjx, Pjy in self.relative_ap_coordinates(point):
            sum_dist += math.sqrt(Pjx ** 2 + Pjy ** 2)
        return sum_dist

    def evaluate_total_distance_of_aps_from_line(self, init_master_coordinates, alpha):
        """
        Calculates the function: sum_{j for all AP} |sin(alpha)Pjx - Pjy|, which gives the sum of the distances of each AP
        from a line identified by init_master_coordinates and alpha.

        :param alpha:
        :return:
        """
        total_dist = 0.0
        for Pjx, Pjy in self.relative_ap_coordinates(init_master_coordinates):
            total_dist += math.fabs(math.sin(alpha) * Pjx - Pjy)
        return total_dist

    def get_best_alpha(self, init_master_coordinates):
        """
        Uses trigonometric equation of a line fitting to init_master_coordinates to find an angle minimizing the sum
        of distances from all AP. alpha in (-pi/2, pi/2)
        Set origo to init_master_coordinates, line: y = tan (alpha) x
        Coordinate of APj in this system: Pjx, Pjy
        Line point distance d(e, APj) = |sin(aplha) Pjx - Pjy|
        Summing up for all APj, the minimum can only be at one of aplha_j = arcsin(Pjy/Pjx)

        :param init_master_coordinates:
        :return:
        """
        mindist = float('inf')
        best_alpha = None
        for Pjx, Pjy in self.relative_ap_coordinates(init_master_coordinates):
            if Pjx == 0.0:
                # This AP contributes a constant to the sum, so its corresponding zerus cannot be min place
                continue
            elif math.fabs(Pjy) > math.fabs(Pjx):
                # we cannot calculate arcsin, this components does not have a zerus
                if Pjx > 0.0:
                    # the component's min is at the beginning of the interval
                    alpha_j = - math.pi / 2.0
                else: # Pjx < 0.0
                    # the component's min is at the end of the interval
                    alpha_j = math.pi / 2.0
            else:
                alpha_j = math.asin(Pjy / Pjx)
            total_dist = self.evaluate_total_distance_of_aps_from_line(init_master_coordinates, alpha_j)
            if total_dist < mindist:
                best_alpha = alpha_j
        if best_alpha is None:
            # it means all APs are lined up and parallel with the x axis
            best_alpha = 0.0
        return best_alpha

    def minimize_direction_of_move(self, init_master_coordinates, dist_in_one_interval):
        """
        Calculates a direction which minimizes the sum of total distances from each access point.
        # NOTE: ignores Earth curveture (unecessarily more difficult maths)
        # NOTE: best direction, i.e. line, does not neccesarily minimizes the distance from a vector, in a more
        sophisticated version best alpha could take move_distance as input too.

        :param init_master_coordinates:
        :param move_distance:
        :return: relative vector to init_master_coordinates
        """
        alpha = self.get_best_alpha(init_master_coordinates)
        vec_len = math.sqrt(math.tan(alpha) ** 2 + 1.0)
        unit_direction = (1 / vec_len, math.tan(alpha) / vec_len)
        # we need to figure out which of the two direction is TOWARDS the majority of the APs
        # shifts p in direction of v by d units
        push_point = lambda p, v, d: (p[0] + v[0]*d, p[1] + v[1]*d)
        # check which direction should we move, by calculating the two possible directions total distance
        if self.total_ap_distance_from_point(push_point(init_master_coordinates, unit_direction, dist_in_one_interval)) > \
            self.total_ap_distance_from_point(push_point(init_master_coordinates, (-unit_direction[0], -unit_direction[1]), dist_in_one_interval)):
            unit_direction = (-unit_direction[0], -unit_direction[1])
        return unit_direction


class ServiceGMLGraph(GMLGraph):

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
        # TODO: maybe use ID-s instead of 'name'
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
        for connected_subgraph in self.get_connected_components():
            try:
                loop = nx.find_cycle(connected_subgraph)
                # assign the first node in the loop as the endpoint of the circular chain
                endpoint_vnf_id = loop[0][0]
                # TODO: add at least one SFC anchored to each cluster endpoint
                endpoint_infra_id = self.random.choice(self.infra.endpoint_ids)
                self.nodes[endpoint_vnf_id][self.location_constr_str] = [endpoint_infra_id]
                # endpoints do not have resources
                self.nodes[endpoint_vnf_id][self.nf_demand_str] = 0

                # save chain latency info to .graph dict
                sfc_delay = self.random.choice(self.sfc_delays)
                # TODO: store in variable instead of gprahs dict! (more direct, NOTE: now only saves one, not all!!
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
