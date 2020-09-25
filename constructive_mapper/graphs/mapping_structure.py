from .generate_service import InfrastructureGMLGraph, ServiceGMLGraph


class VolatileResourcesMapping(dict):

    # key to store a bool for indicating whether it is a successful mapping (taken from the AbstractMapper's earlier realizations)
    WORKED = 'worked'
    # key to store a dict of AP names, for each time instance which is selected to serve the mobility cluster.
    AP_SELECTION = 'AP_selection'
    OBJECTIVE_VALUE = 'Objective_value'
    RUNNING_TIME = 'Running_time'
    EPSILON = 1e-6

    def __init__(self, *args, **kwargs):
        """
        Class to store edge mappings to paths and node mappings. Every item is a node name or tuple of node names.
        Contains 'worked' keyed bool to indicate the success.

        :param args:
        :param kwargs:
        """
        super(VolatileResourcesMapping, self).__init__(*args, **kwargs)
        if VolatileResourcesMapping.WORKED not in self:
            self[VolatileResourcesMapping.WORKED] = False
        if VolatileResourcesMapping.AP_SELECTION not in self:
            # keyed by subinterval index and value is AP name
            self[VolatileResourcesMapping.AP_SELECTION] = {}
        if VolatileResourcesMapping.OBJECTIVE_VALUE not in self:
            self[VolatileResourcesMapping.OBJECTIVE_VALUE] = None
        if VolatileResourcesMapping.RUNNING_TIME not in self:
            self[VolatileResourcesMapping.RUNNING_TIME] = None

    def __repr__(self):
        return "VolatileResourcesMapping(Feasible: {}, Obj.value: {}, Runtime: {})".\
            format(self[self.WORKED], self[self.OBJECTIVE_VALUE], self[self.RUNNING_TIME])

    def __str__(self):
        return self.__repr__()

    def add_access_point_selection(self, subinterval : int, ap_name):
        self[VolatileResourcesMapping.AP_SELECTION][int(subinterval)] = ap_name

    def get_access_point_selection(self, subinterval : int):
        return self[VolatileResourcesMapping.AP_SELECTION][int(subinterval)]

    def get_hosting_infra_node_id(self, ns : ServiceGMLGraph, infra : InfrastructureGMLGraph, vnf_id):
        """
        Returns the infra node id, where the given VNF id is hosted. Could be cached...

        :param ns:
        :param infra:
        :param vnf_id:
        :return:
        """
        for vnf_name, host_name in self.items():
            if ns.nodes[vnf_id][ns.node_name_str] == vnf_name:
                for host_id, data in infra.nodes(data=True):
                    if data[infra.node_name_str] == host_name:
                        return host_id

    def validate_mapping(self, ns: ServiceGMLGraph, infra: InfrastructureGMLGraph,
                         time_interval_count, coverage_threshold, battery_threshold, **kwargs):
        """
        Checks whether the mapping task defined by the ns and infra is solved by this mapping object

        :param ns:
        :param infra:
        :param kwargs: some optimization parameters of the solution provided by the heuristic are irrelevant for the validation
        :return:
        """
        if self[VolatileResourcesMapping.WORKED]:

            # if not all service nodes are mapped
            if not all({d[ns.node_name_str] in self for n, d in ns.nodes(data=True)}):
                return False
            if len(self[VolatileResourcesMapping.AP_SELECTION]) != infra.time_interval_count:
                return False
            # check AP selection
            for subinterval in range(1, time_interval_count+1):
                ap_name = self.get_access_point_selection(subinterval)
                # find the AP_id for this AP name
                for ap_id in infra.access_point_ids:
                    if infra.nodes[ap_id][infra.node_name_str] == ap_name:
                        for master_mobile_id in infra.ap_coverage_probabilities.keys():
                            if infra.ap_coverage_probabilities[master_mobile_id][subinterval][ap_id] < coverage_threshold:
                                return False

                        # check delay constraints in each interval for all subchains
                        for sfc_delay, sfc_path in ns.sfc_delays_list:
                            actual_sfc_delay = 0.0
                            for nfu, nfv in sfc_path:
                                host_u, host_v = self.get_hosting_infra_node_id(ns, infra, nfu), self.get_hosting_infra_node_id(ns, infra, nfv)
                                actual_sfc_delay += infra.delay_distance(host_u, host_v, subinterval, coverage_threshold, ap_id)
                            if sfc_delay + self.EPSILON < actual_sfc_delay:
                                return False
                        # go to next subinterval
                        break
                else:
                    raise Exception("No AP id found for name {} in subinterval {}".format(ap_name, subinterval))

            # location constraints
            for nf, data in ns.nodes(data=True):
                if ns.location_constr_str in data:
                    location_constr_name = map(lambda x: infra.nodes[x][infra.node_name_str], data[ns.location_constr_str])
                    if self[data[ns.node_name_str]] not in location_constr_name:
                        return False

            mobile_ids = list(infra.mobile_ids)
            # check capacity constraints
            for infra_node_id in infra.nodes():
                total_capacity = infra.nodes[infra_node_id][infra.infra_node_capacity_str]
                infra_node_name = infra.nodes[infra_node_id][infra.node_name_str]
                allocated_load = 0.0
                for vnf_id, data in ns.nodes(data=True):
                    if self[data[ns.node_name_str]] == infra_node_name:
                        allocated_load += data[ns.nf_demand_str]
                # check if load matches
                if allocated_load > total_capacity + self.EPSILON:
                    return False
                # check battery constraints
                if infra_node_id in infra.mobile_ids:
                    mobile_ids.remove(infra_node_id)
                    linear_coeff = infra.unloaded_battery_alive_prob - infra.full_loaded_battery_alive_prob
                    probability = infra.unloaded_battery_alive_prob - allocated_load / total_capacity * linear_coeff
                    if probability < battery_threshold - self.EPSILON:
                        return False
            if len(mobile_ids) > 0:
                raise Exception("Not all mobile nodes have been checked for battery constraints!")

            # if we didnt return yet, all constraints are correct
            return True
        else:
            # if mapping is not 'worked' then it is valid.
            return True
