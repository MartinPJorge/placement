import networkx as nx
import random
import math
import sys
import logging
from rainbow_logging_handler import RainbowLoggingHandler


class GMLGraph(nx.DiGraph):

    def __init__(self, incoming_graph_data=None, gml_file=None, label='label', log=None, **attr):
        if log is None:
            self.log = logging.Logger(self.__class__.__name__)
            handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
            formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
            handler.setFormatter(formatter)
            self.log.addHandler(handler)
            self.log.setLevel(logging.DEBUG)
        else:
            self.log = log.getChild(self.__class__.__name__)
            for handler in log.handlers:
                self.log.addHandler(handler)
            self.log.setLevel(log.getEffectiveLevel())
        if gml_file is not None:
            super(GMLGraph, self).__init__(incoming_graph_data=nx.read_gml(gml_file, label=label), **attr)
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
        # NOTE: this is nasty, if causes problems anywhere else, we can figure out a better way to call weakly_connected_component_subgraphs
        tmp_class_name = self.__class__
        self.__class__ = nx.DiGraph
        cc = list(nx.weakly_connected_component_subgraphs(self))
        self.__class__ = tmp_class_name
        return cc


class InfrastructureGMLGraph(GMLGraph):

    def __init__(self, incoming_graph_data=None, gml_file=None, label='label', seed=0, cluster_move_distances=None, cluster_move_waypoints=None,
                 coverage_blocking_areas=None,
                 time_interval_count=None, unloaded_battery_alive_prob=0.99, full_loaded_battery_alive_prob=0.2, **attr):
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
        self.node_name_str = 'name'
        self.infra_node_capacity_str = 'cpu'
        self.infra_fixed_cost_str = 'fixed_cost'
        self.infra_unit_cost_str = 'cost'
        self.endpoint_type_str = 'endpoint'
        self.type_str = 'type'
        self.server_type_str = 'server'
        self.access_point_type_str = 'cell'
        self.access_point_delay_str = 'delay'
        # NOTE: this must not be confused with the fixed/unit cost if AP-s would ever be used for hosting some NFs
        self.access_point_usage_cost_str = 'cost'
        self.link_delay_str = 'delay'
        # the distance which the AP wireless connectivity reaches with high reliability
        # reach is given in meters, one degree corresponds to 111 139m
        self.one_degree_in_meters = 111139.0
        self.ap_reach_str = 'coverageRadius'
        # These might have multiple types, just like the switches and servers!
        self.access_point_strs = ['pico_cell', 'micro_cell', 'macro_cell', 'cell']
        self.server_strs = ['m{}_server'.format(i) for i in range(1,4)]
        self.server_strs.append('server')
        self.mobile_node_str = 'fogNode'

        super(InfrastructureGMLGraph, self).__init__(incoming_graph_data, gml_file=gml_file, label=label, **attr)
        # NOTE: duplication of information storage should be avoided (do not store information in class attributes, which can de
        # directly accessed at the network x dicts of the class. Only create attributes, if if they need calculation based on the
        # input information in the GML file (i.e. mobility pattern)
        self.random = random.Random(seed)
        self.unloaded_battery_alive_prob = unloaded_battery_alive_prob
        self.full_loaded_battery_alive_prob = full_loaded_battery_alive_prob

        # store ID-s of all relevant node types
        self.endpoint_ids, self.access_point_ids, self.server_ids, self.mobile_ids, self.ignored_nodes_for_optimization = [], [], [], [], []
        for n, node_dict in self.nodes(data=True):
            # TODO: read fixed_cost info from the GML file if needed!
            node_dict[self.infra_fixed_cost_str] = 0.0
            if node_dict[self.type_str] == self.endpoint_type_str:
                self.endpoint_ids.append(n)
            elif node_dict[self.type_str] in self.access_point_strs:
                self.access_point_ids.append(n)
            elif node_dict[self.type_str] in self.server_strs:
                self.server_ids.append(n)
            elif node_dict[self.type_str] == self.mobile_node_str:
                #
                self.mobile_ids.append(n)
            else:
                # save all nodes, in some set, beacuse these ones needs to be ignored during adding them to the AMPL model
                self.ignored_nodes_for_optimization.append(n)
        self.cluster_endpoint_ids = []
        # stores lists of the contained mobile ID-s for each cluster.
        # Its key is the same as the outer key of the self.ap_coverage_probabilities
        self.mobile_cluster_id_to_node_ids = {}
        # contains dictionary for each mobile cluster which is a dict of each time instance which is
        # a dict of each AP_id to their coverage probability. A mobile cluster is identified by one of its nodes (master node),
        # which relays the traffic of all mobile nodes towars the fixed part of the infra.
        self.ap_coverage_probabilities = {}
        self.coverage_blocking_areas = coverage_blocking_areas
        if cluster_move_distances is not None:
            self.generate_mobility_pattern(cluster_move_distances)
        elif cluster_move_waypoints is not None:
            if self.coverage_blocking_areas is None:
                raise Exception("Coverage blocking areas must be given if cluster move waypoints are given.")
            else:
                # list of 4-tuples of 2-tuples of floats, in order topleft, topright, bottomright, bottomleft
                self.coverage_blocking_areas_coords = [((40.271401, -3.752911), (40.271360, -3.751570), (40.269780, -3.751132), (40.270615, -3.752761))]
            # TODO: open and process the waypoints
            self.generate_mobility_pattern_from_waypoints([(40.269342, -3.753353), (40.270131, -3.752146), (40.271217, -3.750646), (40.270353, -3.750454)])
        # Calculate on all unconnected components (i.e between the nodes of each clusters and the fixed part)
        self.shortest_paths_fixed_part = dict(nx.all_pairs_dijkstra_path_length(self, weight=self.link_delay_str))

    def check_graph(self):
        """
        # TODO: check if this format complies to the AMPL converter and the ConstructiveMapperFromFractional's desired format.

        :return:
        """
        return True

    def delay_distance(self, u, v, time_interval_index=None, coverage_prob=None, through_ap_id=None):
        """
        Reads the precalculated distances measured in delay between any two nodes of the infrastructure.
        'through_ap_id' and 'coverage_prob' can be specified in any combination.
        E.g.: if u and v are both in the fixed infrastructure, through_ap_id and coverage_prob are ignored.

        :param time_interval_index:
        :param u:
        :param v:
        :param coverage_prob: provides a filter on the AP-s which might be used for the delay calculation
        :param through_ap_id: ID of the AP, which should be used for communication if u and v are separated by wireless connections
        :return:
        """
        all_cluster_ids = self.cluster_endpoint_ids + self.mobile_ids
        if v in self.shortest_paths_fixed_part[u]:
            # if we are between two nodes of the same component (inside cluster or inside fixed infrastructure), no AP-s need to be used.
            return self.shortest_paths_fixed_part[u][v]
        elif u in all_cluster_ids and v in all_cluster_ids:
            # mobile clusters cannot communicate with each other (for now)
            return float('inf')
        elif time_interval_index is None:
            raise ValueError("time_interval_index must be given if u and v are not among the same parts of the infra!")
        else:
            # we are between a mobile cluster and the fixed infra
            # It is symmetric for the direction so make u: mobile and v: fixed
            if v in all_cluster_ids:
                tmp_u = u
                u = v
                v =tmp_u
            # find which cluster are we in with the 'u'
            affected_master_mobile_id = None
            for master_mobile_id in self.mobile_cluster_id_to_node_ids.keys():
                if u in self.mobile_cluster_id_to_node_ids[master_mobile_id]:
                    affected_master_mobile_id = master_mobile_id
                    break
            if through_ap_id is not None:
                # if a coverage probability is given, only return the delay, if the given AP's coverage meets the specified threshold
                if coverage_prob is not None:
                    if coverage_prob > self.ap_coverage_probabilities[affected_master_mobile_id][time_interval_index][through_ap_id]:
                        return float('inf')
                chosen_ap_delay = self.nodes[through_ap_id][self.access_point_delay_str]
                chosen_ap_id = through_ap_id
            else:
                # find the AP with the lowest delay, which is above the given coverage threshold
                chosen_ap_delay = float('inf')
                chosen_ap_id = None
                for ap_id in self.access_point_ids:
                    current_ap_delay = self.nodes[ap_id][self.access_point_delay_str]
                    if coverage_prob is not None:
                        # if coverage is given, skip the ones which are lower.
                        if coverage_prob > self.ap_coverage_probabilities[affected_master_mobile_id][time_interval_index][ap_id]:
                            continue
                    if chosen_ap_delay > current_ap_delay:
                        chosen_ap_delay = current_ap_delay
                        chosen_ap_id = ap_id
                # if no allowed AP ID is found, distance is infinite
                if chosen_ap_id is None:
                    return float('inf')
            # the final distance is given by the sum of the three minimized parts.
            return self.shortest_paths_fixed_part[u][affected_master_mobile_id] +\
                    chosen_ap_delay +\
                    self.shortest_paths_fixed_part[chosen_ap_id][v]

    def generate_mobility_pattern(self, cluster_move_distances):
        """
        Calculates the coverage probabilities of each cluster in each time instance by each AP.
        A simple pattern is used: the cluster moves in a line distance specified in cluster_move_distances and moves back to the
        starting point by the end of the simulated time interval.

        :return:
        """
        # TODO: if compatibility with this cluster move distances and waypoints should be kept, might be some refactoring to avoid code duplication.
        # so we wont modify the input parameter by .pop()
        cluster_move_distances = list(cluster_move_distances)
        for connected_comp in self.get_connected_components():
            # see if this is a mobile node cluster
            if any(m in connected_comp for m in self.mobile_ids):
                # there must be at least one endpoint in each cluster
                endpoints_in_component = list(filter(lambda m: m in self.endpoint_ids, connected_comp.nodes))
                if len(endpoints_in_component) == 0:
                    raise Exception("No endpoint found in mobile cluster {}".format(connected_comp.nodes))
                else:
                    endpoint = self.random.choice(endpoints_in_component)
                self.cluster_endpoint_ids.append(endpoint)
                master_mobile = self.random.choice([m for m in filter(lambda m: m in self.mobile_ids, connected_comp.nodes)])
                self.log.debug("Generating mobility pattern for mobile cluster with master {}".format(master_mobile))
                self.mobile_cluster_id_to_node_ids[master_mobile] = list(connected_comp.nodes()) + [endpoint]
                self.ap_coverage_probabilities[master_mobile] = {}
                move_distance = cluster_move_distances.pop()
                dist_in_one_interval = 2 * move_distance / float(self.time_interval_count)
                init_master_coordinates = (self.nodes[master_mobile]['lat'], self.nodes[master_mobile]['lon'])
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
                    self.add_all_coverage_probs(master_mobile, time_interval_idx, current_p)

    def distance_to_raw_probability_1(self, dist, ap_reach):
        return - (dist / (ap_reach)) ** 2 + 1.0

    def distance_to_raw_probability_2(self, dist, ap_reach):
        if dist < ap_reach:
            return - (dist / 20.0 / ap_reach) + 1.0
        else:
            return - (5.0 * 0.95 * dist / ap_reach) + 4.0 * 0.95

    def get_coverage_probability(self, current_mobile_pos, ap_id, check_LoS=False):
        """
        Calculates the probabilty of covering the mobile node in its current position by the given AP.
        Uses the reach of the AP to get the probability. If the mobile position is on the border of the reach the
        probability drastically drops.

        :param current_mobile_pos:
        :param ap_id:
        :return:
        """
        ap_data = self.nodes[ap_id]
        if check_LoS:
            if not self.is_line_of_sight(current_mobile_pos, (ap_data['lat'], ap_data['lon'])):
                return 0.0
        Pjx, Pjy = self.relative_coordinates(current_mobile_pos, ap_data)
        dist = math.sqrt(Pjx ** 2 + Pjy ** 2)
        # AP reach is given in meters, but we need it in degrees
        reach = self.nodes[ap_id][self.ap_reach_str] / self.one_degree_in_meters

        # TODO: get better model for coverage probability dropping based on research
        # drops to 0.0 probability somewhere after 20% beyond the reach of the AP, decreases squared from 1.0
        probability = 1.0
        raw_probability = self.distance_to_raw_probability_2(dist, reach)
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
        Calculates the function: sum_{j for all AP} cos(aplha)|tan(alpha)Pjx - Pjy|, which gives the sum of the distances of each AP
        from a line identified by init_master_coordinates and alpha.

        :param alpha:
        :return:
        """
        total_dist = 0.0
        for Pjx, Pjy in self.relative_ap_coordinates(init_master_coordinates):
            total_dist += math.cos(alpha) * math.fabs(math.tan(alpha) * Pjx - Pjy)
        return total_dist

    def get_best_alpha(self, init_master_coordinates):
        """
        Uses trigonometric equation of a line fitting to init_master_coordinates to find an angle minimizing the sum
        of distances from all AP. alpha in (-pi/2, pi/2)
        Set origo to init_master_coordinates, line: y = tan (alpha) x
        Coordinate of APj in this system: Pjx, Pjy
        Line 0 = Ax + By + C distance from point P=(x0,y0): |Ax0 + By0 + C| / sqrt(A**2 + B**2)
        Line point distance d(e, APj) = cos(alpha) |tan(aplha) Pjx - Pjy|
        Summing up for all APj, the minimum can only be at one of aplha_j = arctan(Pjy/Pjx)

        :param init_master_coordinates:
        :return:
        """
        mindist = float('inf')
        best_alpha = None
        for Pjx, Pjy in self.relative_ap_coordinates(init_master_coordinates):
            if Pjx == 0.0:
                # This AP contributes a constant to the sum, so its corresponding zerus should not be min place
                alpha_j = math.pi / 2
            else:
                # This components zerus place might be a minimal place for the whole function
                alpha_j = math.atan(Pjy / Pjx)
            total_dist = self.evaluate_total_distance_of_aps_from_line(init_master_coordinates, alpha_j)
            if total_dist < mindist:
                best_alpha = alpha_j
                mindist = total_dist
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

    def generate_mobility_pattern_from_waypoints(self, cluster_waypoints):
        """
        Calculates the coverage probabilities of the cluster in each time instance by each AP.
        The cluster moves in straight lines between the cluster waypoints.

        :return:
        """
        for connected_comp in self.get_connected_components():
            # see if this is a mobile node cluster
            if any(m in connected_comp for m in self.mobile_ids):
                # there must be at least one endpoint in each cluster
                endpoints_in_component = list(filter(lambda m: m in self.endpoint_ids, connected_comp.nodes))
                if len(endpoints_in_component) == 0:
                    raise Exception("No endpoint found in mobile cluster {}".format(connected_comp.nodes))
                else:
                    endpoint = self.random.choice(endpoints_in_component)
                self.cluster_endpoint_ids.append(endpoint)
                master_mobile = self.random.choice([m for m in filter(lambda m: m in self.mobile_ids, connected_comp.nodes)])
                self.log.debug("Generating mobility pattern for mobile cluster with master {}".format(master_mobile))
                self.mobile_cluster_id_to_node_ids[master_mobile] = list(connected_comp.nodes()) + [endpoint]
                self.ap_coverage_probabilities[master_mobile] = {}
                # shifts p in direction of v by d units
                push_point = lambda p, v, d: (p[0] + v[0]*d, p[1] + v[1]*d)
                if len(cluster_waypoints) < 2:
                    raise Exception("There must be at least 2 waypoints in the mobility pattern!")
                total_path_length = 0
                for wayp1, wayp2 in zip(cluster_waypoints[:-1], cluster_waypoints[1:]):
                    total_path_length += self.length_of_segment(wayp1, wayp2)
                move_dist_one_interval = total_path_length / self.time_interval_count
                waypoint_dist_compensation = 0
                for subinterval_index in range(1, self.time_interval_count+1):
                    move_from_wayp1 = move_dist_one_interval
                    for wayp1, wayp2 in zip(cluster_waypoints[:-1], cluster_waypoints[1:]):
                        wayp_dist = self.length_of_segment(wayp1, wayp2) - waypoint_dist_compensation
                        if move_from_wayp1 > wayp_dist:
                            move_from_wayp1 -= wayp_dist
                            # after reaching the wayp2, we do not need distance compensation
                            waypoint_dist_compensation = 0
                        else:
                            # in the next interval we need to move this much less between these endpoints
                            waypoint_dist_compensation = move_from_wayp1
                            break
                    # we know we need to move from wayp1 to the direction of wayp2 a distance of move_from_wayp1
                    # NOTE: wayp-s are defined here, becuase there are at least 2 waypoints!
                    wayp_dist = self.length_of_segment(wayp1, wayp2)
                    move_direction = ((wayp2[0])-wayp1[0], (wayp2[1])-wayp1[1])
                    current_p = push_point(wayp1, move_direction, move_from_wayp1/wayp_dist)
                    self.add_all_coverage_probs(master_mobile, subinterval_index, current_p, check_LoS=True)

    def add_all_coverage_probs(self, master_mobile, subinterval_index, current_p, check_LoS=False):
        self.ap_coverage_probabilities[master_mobile][subinterval_index] = {}
        for ap_id in self.access_point_ids:
            self.ap_coverage_probabilities[master_mobile][subinterval_index][ap_id] = \
                self.get_coverage_probability(current_p, ap_id, check_LoS)

    def length_of_segment(self, x1y1, x2y2):
        """
        Calculates the length of a segment defined by the two points

        :param x1y1:
        :param x2y2:
        :return:
        """
        x1, y1 = x1y1
        x2, y2 = x2y2
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

    def does_segments_intersect(self, x1y1, x2y2, u1v1, u2v2):
        """
        Checks if two line segments between the defined points are intersecting inside the segments.
        y = ax + c is the line through points x1y1, x2y2
        y = bx + d is the line through points u1v1, u2v2

        :param x1y1:
        :param x2y2:
        :param u1v1:
        :param u2v2:
        :return:
        """
        x1, y1 = x1y1
        x2, y2 = x2y2
        xy_len = self.length_of_segment(x1y1, x2y2)
        u1, v1 = u1v1
        u2, v2 = u2v2
        uv_len = self.length_of_segment(u1v1, u2v2)
        # Get intersection of a y = mx + b and x=x_axis_intersection lines.
        get_intersection_of_yaxis_parallel = lambda x_0, m, b: (x_0, m * x_0 + b)
        if x1 == x2:
            if u1 == u2:
                # both lines are parallel to the y axis
                return False
            else:
                m = (v2 - v1) / (u2 - u1)
                intersection = get_intersection_of_yaxis_parallel(x1, m, v1-m*u1)
        else:
            a = (y2 - y1) / (x2 - x1)
            c = y1 - a * x1
            if u1 == u2:
                intersection = get_intersection_of_yaxis_parallel(u1, a, c)
            else:
                b = (v2 - v1) / (u2 - u1)
                d = v1 - b * u1
                if a == b:
                    # the lines have the same angle (it might happen that they are exactly on each other, but we can handle it as it is
                    # in the LOS)
                    return False
                else:
                    intersection = ((d - c) / (a - b),
                                    (a*d - b*c) / (a - b))
        # the intersection is on the xy segment and on  the uv segment (this works in any parallel cases too!)
        if self.length_of_segment(x1y1, intersection) < xy_len and self.length_of_segment(x2y2, intersection) < xy_len and\
                    self.length_of_segment(u1v1, intersection) < uv_len and self.length_of_segment(u2v2, intersection) < uv_len:
            return True
        else:
            return False

    def is_line_of_sight(self, P1, P2):
        """
        Checks if the line between the P1 and P2 points blocked by any of the coverage blocking areas.

        :param P1:
        :param P2:
        :return:
        """
        for cov_block_area in self.coverage_blocking_areas_coords:
            tl, tr, br, bl = cov_block_area
            number_of_segment_intersections = 0
            # iterate on all sides of a block
            for block_p1, block_p2 in zip([tl, tr, br, bl], [tr, br, bl, tl]):
                if self.does_segments_intersect(P1, P2, block_p1, block_p2):
                    number_of_segment_intersections += 1
            if number_of_segment_intersections == 1:
                raise Exception("Intersecting only one side of a coverage blocking area, meaning {} or {} is inside {}".
                                format(P1, P2, cov_block_area))
            elif number_of_segment_intersections == 0:
                return True
            elif number_of_segment_intersections == 2:
                return False
            else:
                raise Exception("Intersecting more than 2 sides of a rectangle should not be possible!")


class ServiceGMLGraph(GMLGraph):

    def __init__(self, infra: InfrastructureGMLGraph, connected_component_sizes, sfc_delays, seed, series_parallel_ratio,
                 mobile_nfs_per_sfc=0, incoming_graph_data=None, **attr):
        """
        Generates a service using series parallel graph structures with SFC-s on its paths on top of infra with parameters given.

        :param seed: randomization seed
        :param series_parallel_ratio:
        :param sfc_delays: list of delay values, which the chains can take
        :param infra:
        :param incoming_graph_data: If it is given, additional elements are created at the nx.DiGraph
        :param connected_component_sizes: list of integers describing the number and size of the connected service graph components
        :param mobile_nfs_per_sfc: The number of NFs in each SFC which must be located in the corresponding mobile cluster
                                   (if a chain is shorter, at most all of the NFs are set but not more).
        :param attr:
        """
        # =====================  attribute strings =================== #
        self.nf_demand_str = 'weight'
        self.node_name_str = 'name'
        self.location_constr_str = 'location_constraints'   # list of node ids, where an NF may be mapped

        super(ServiceGMLGraph, self).__init__(incoming_graph_data=incoming_graph_data, **attr)
        self.connected_component_sizes = connected_component_sizes
        self.sfc_delays = sfc_delays
        self.infra = infra
        self.random = random.Random(seed)
        self.current_node_id = 0
        self.series_parallel_ratio = series_parallel_ratio
        self.sfc_delays_list = []             # list of (delay, edge path) tuples containing chain delays.
        self.mobile_nfs_per_sfc = mobile_nfs_per_sfc
        self._generate_structure()
        self.vnfs= [v[self.node_name_str] for _, v in self.nodes(data=True)]

    def get_node_name(self, id):
        return 'nf' + str(id)

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
            self.add_node(u, weight=self.random.uniform(0.5, 1.05), name=self.get_node_name(u))
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

    def _set_location_constraints(self, edge_list_of_loop, endpoint_infra_id):
        """
        Sets location bounds for the first/last self.mobile_nfs_per_sfc pieces of NFs to be only mappable to the
        corresponding mobile node cluster, identified by endpoint_infra_id.

        :param edge_list_of_loop:
        :param endpoint_infra_id:
        :return:
        """
        for cluster_node_ids in self.infra.mobile_cluster_id_to_node_ids.values():
            if endpoint_infra_id in cluster_node_ids:
                location_bound_nfs = 0
                node_list = [u for u, v in edge_list_of_loop]
                # the first element is mapped (with location constraints) to the endpoint
                loop_nf_ids = list(node_list)[1:]
                for begin_end_tuple in zip(loop_nf_ids, reversed(loop_nf_ids)):
                    # add NFs from beginning and ending of the chain alternating
                    for nf_id in begin_end_tuple:
                        # keep adding location bounds until we reach the required amount AND we have any more NF which are not set.
                        if location_bound_nfs < self.mobile_nfs_per_sfc and len(loop_nf_ids) - location_bound_nfs > 0:
                            # NOTE: make a copy of the list for every location bound node
                            self.nodes[nf_id][self.location_constr_str] = list(cluster_node_ids)
                            location_bound_nfs += 1
                        else:
                            return
                # after we found the correspoing cluster we have nothing left to do
                return

    def _add_service_function_loops(self):
        """
        Add an SFC with generated end to end delay starting from an endpoint and ending in one.
        Cluster endpoints are always used.

        :return:
        """
        infra_endpoints = list(self.infra.cluster_endpoint_ids)
        non_cluster_endpoints = [e for e in self.infra.endpoint_ids if e not in self.infra.cluster_endpoint_ids]
        self.random.shuffle(non_cluster_endpoints)
        infra_endpoints.extend(non_cluster_endpoints)
        if len(self.connected_component_sizes) > len(infra_endpoints):
            raise Exception("There are more components in the service graph than enpoints in the infra")
        loop_sfc_count = 0
        for connected_subgraph in self.get_connected_components():
            try:
                loop = nx.find_cycle(connected_subgraph)
                # assign the first node in the loop as the endpoint of the circular chain
                endpoint_vnf_id = loop[0][0]
                # first endpoint_infra_ids are from the clusters, so we start adding SFC-s from their endpoints
                endpoint_infra_id = infra_endpoints[loop_sfc_count]
                loop_sfc_count += 1
                self.nodes[endpoint_vnf_id][self.location_constr_str] = [endpoint_infra_id]
                # endpoints do not have resources
                self.nodes[endpoint_vnf_id][self.nf_demand_str] = 0
                sfc_delay = self.random.choice(self.sfc_delays)
                self._set_location_constraints(loop, endpoint_infra_id)
                # Save SFC-s as tuples of delay and their vnf id path
                self.sfc_delays_list.append((sfc_delay, loop))
                self.log.debug("Adding SFC from VNF {} to endpoint {} with delay {} on path {}".
                               format(endpoint_vnf_id, endpoint_infra_id, sfc_delay, loop))
            except nx.NetworkXNoCycle:
                # warn, so we can expect to have same number of SFC-s as connected components
                self.log.warn("No cycle found in component of size {}".format(connected_subgraph.number_of_nodes()))

    def _generate_structure(self):
        """
        Creates the overall structure of the service graph containing multiple connected components

        :return:
        """
        for n in self.connected_component_sizes:
            self.generate_series_parallel_graph(n)
        self._add_service_function_loops()
