from .support_classes import *


class BaseConstraintViolationChecker(metaclass=ABCMeta):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function, log=None):
        super(BaseConstraintViolationChecker, self).__init__()
        self.bins = bins
        self.items = items
        self.ns = ns
        self.infra = infra
        self.violating_items = None
        self.id_item_map = {i['id'] : i for i in self.items}
        # function which executes an item move in the (global) bin mapping structure
        self.item_move_function = item_move_function
        if log is not None:
            self.log = log.getChild(self.__class__.__name__)
            for handler in log.handlers:
                self.log.addHandler(handler)
            self.log.setLevel(log.getEffectiveLevel())

    @abstractmethod
    def get_violating_items(self) -> list:
        """
        Returns a list of items which somehow violate the constraints, sets the elf.violating_items list.

        :return:
        """
        pass

    @abstractmethod
    def item_move_improvement_score(self, item_to_be_moved : Item, target_bin : Bin) -> int:
        """
        Returns +1, 0, -1 to indicate whether the input item move is desired, neutral or undesired for easing
        the violation of this constraint.

        :param item_to_be_moved:
        :param target_bin:
        :return:
        """
        pass


class BinCapacityViolationChecker(BaseConstraintViolationChecker):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function):
        super(BinCapacityViolationChecker, self).__init__(items, bins, infra, ns, item_move_function)

    def get_violating_items(self):
        """
        Returns all items, which are in overloaded bins.

        :return:
        """
        violating_items = []
        for bin in self.bins:
            if bin.is_overloaded:
                violating_items.extend(bin.mapped_here)
        return violating_items

    def item_move_improvement_score(self, item_to_be_moved: Item, target_bin: Bin):
        """
        Prefers if the number of violating items/violated bins decrease.

        :param item_to_be_moved:
        :param target_bin:
        :return:
        """
        origin_bin_not_overloaded = item_to_be_moved.mapped_to.total_load - item_to_be_moved['weight'] < \
                                    item_to_be_moved.mapped_to['capacity']
        if target_bin.does_item_fit(item_to_be_moved):
            return 1
        elif origin_bin_not_overloaded:
            return 0
        else:
            # NOTE: it is possible that the total number of violating items wont increase in this case either, if there was no item mapped
            # to target bin, but then it still doesnot make sense it map a not fitting item there.
            return -1


class DelayAndCoverageViolationChecker(BaseConstraintViolationChecker):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function, sfc_delay, sfc_path,
                 time_interval_count, coverage_threshold, shared_ap_selection : InvalidableAPSelectionStruct, log):
        super(DelayAndCoverageViolationChecker, self).__init__(items, bins, infra, ns, item_move_function, log)
        self.sfc_delay = sfc_delay
        self.sfc_path = sfc_path
        self.affected_nfs = [v for u,v in self.sfc_path]
        self.coverage_threshold = coverage_threshold
        self.time_interval_count = time_interval_count
        # stores the AP id for each time interval which, has the lowest delay, obeying the coverage probability
        # The variable needs to be shared among all instances of the class, because the AP selection must agree for all SFC-s.
        # From this point on, any instance of the class is executed,
        # it must give the same AP selection in all subintervals OR set it back to invalid, if its constraint is violated.
        self.chosen_ap_ids = shared_ap_selection
        self.EPSILON = 1e-5

    def get_cheapest_ap_id(self, subinterval):
        """
        Choose the cheapest AP which meets the coverage threshold. We still need to choose an access point, even if we do not need to
        communicate though the wireless channel.
        Returns None if no such AP exists.

        :param subinterval:
        :return:
        """
        master_mobile_id = list(self.infra.ap_coverage_probabilities.keys())[0]
        min_ap_cost = float('inf')
        min_cost_ap_id = None
        for ap_id, coverage_prob in self.infra.ap_coverage_probabilities[master_mobile_id][subinterval].items():
            if coverage_prob > self.coverage_threshold + self.EPSILON:
                ap_cost = self.infra.nodes[ap_id][self.infra.access_point_usage_cost_str]
                if ap_cost + self.EPSILON < min_ap_cost:
                    min_ap_cost = ap_cost
                    min_cost_ap_id = ap_id
        return min_cost_ap_id

    def calculate_violations(self):
        """
        Calculates the number of violating time intervals in the current allocation, respecting the coverage probability,
        described by a tuple:
            (number of subintervals, where the SFC delay is infinite;
            number of subintervals, where remaining SFC delay is negative)
        Second number is only informative, if the first number is 0.
        Updates the shared chosen_ap_ids struct to reflect the violation metrics returned by the function.

        :return: int tuple
        """
        remaining_delay = float(self.sfc_delay)
        all_mobile_node_ids = self.infra.cluster_endpoint_ids + self.infra.mobile_ids
        negative_rem_delay_subinterval = 0
        # VNFs cannot be mapped to APs, ID-s which are connected to the fixed infra part are not stored separately
        all_fixed_node_ids = self.infra.server_ids + [n for n in self.infra.endpoint_ids if n not in self.infra.cluster_endpoint_ids]
        for u, v in self.sfc_path:
            u_host_id = self.id_item_map[u].mapped_to['id']
            v_host_id = self.id_item_map[v].mapped_to['id']
            # collect the time/place independent latency the current allocation
            if (u_host_id in all_mobile_node_ids and v_host_id in all_mobile_node_ids) or\
                (u_host_id in all_fixed_node_ids and v_host_id in all_fixed_node_ids):
                remaining_delay -= self.infra.delay_distance(u_host_id, v_host_id)
        if remaining_delay == -float('inf') or remaining_delay == float('inf'):
            raise Exception("Remaining delay cannot be -inf or inf at this point!")
        if remaining_delay + self.EPSILON < 0:
            # if the delay is already negative in the fixed delay, then it will be negative in all intervals
            negative_rem_delay_subinterval = self.time_interval_count

        inf_count_subinterval = 0
        # stores the AP id for each time interval which, has the lowest delay, obeying the coverage probability
        current_chosen_ap_ids = dict()
        for subinterval in range(1, self.time_interval_count+1):
            rem_delay_in_subint = remaining_delay
            min_delay_though_ap_id = None
            for u, v in self.sfc_path:
                u_host_id = self.id_item_map[u].mapped_to['id']
                v_host_id = self.id_item_map[v].mapped_to['id']
                # filter for links mapped over the wireless channel
                if (u_host_id in all_mobile_node_ids and v_host_id in all_fixed_node_ids) or \
                        (u_host_id in all_fixed_node_ids and v_host_id in all_mobile_node_ids):
                    # find the best possible delay, which obeys the coverage probabilty through ANY access point.
                    # NOTE: We cannot select the cheapest AP, even if there are multiple access points which obey the delay requirement,
                    # because then multiple SFC delays could result in different AP selections. So we need to select the lowest delay one
                    # and save it in a shared variable
                    # NOTE: other option to find the lowest delay SFC and for all other SFC choose the cheapest (deterministically)
                    # which is below the lowest delay. Requires more coordination bentween SFC violation checkers
                    min_wireless_delay_with_cov = float('inf')
                    for ap_id in self.infra.access_point_ids:
                        curr_wireless_delay_with_cov = self.infra.delay_distance(u_host_id, v_host_id, subinterval,
                                                                                 self.coverage_threshold, ap_id)
                        if curr_wireless_delay_with_cov + self.EPSILON < min_wireless_delay_with_cov:
                            min_wireless_delay_with_cov = curr_wireless_delay_with_cov
                            min_delay_though_ap_id = ap_id
                    # evaluate the situation for the output numbers
                    if min_wireless_delay_with_cov == float('inf'):
                        inf_count_subinterval += 1
                    # we should not go above the negative remaining delay intervals above the total number of intervals
                    elif rem_delay_in_subint + self.EPSILON < min_wireless_delay_with_cov and \
                            negative_rem_delay_subinterval < self.time_interval_count:
                        negative_rem_delay_subinterval += 1
                    else:
                        rem_delay_in_subint -= min_wireless_delay_with_cov
            if inf_count_subinterval == 0 and negative_rem_delay_subinterval == 0:
                if min_delay_though_ap_id is not None:
                    current_chosen_ap_ids[subinterval] = min_delay_though_ap_id
                elif remaining_delay == rem_delay_in_subint:
                    # if all nodes are mapped inside the cluster or inside the fixed infra part, we still need to select an AP
                    cheapest_ap_id = self.get_cheapest_ap_id(subinterval)
                    if cheapest_ap_id is not None:
                        current_chosen_ap_ids[subinterval] = cheapest_ap_id
                    else:
                        # if AP cannot be selected (due to only coverage criteria, this is a bad mapping in this subinterval
                        inf_count_subinterval += 1
                        self.chosen_ap_ids.invalidate()
                else:
                    raise Exception("AP must always be selected if the delay and coverage are OK in a mapping!")
            else:
                self.chosen_ap_ids.invalidate()

        # if the delay and coverage values are violated in none of the subintervals, then we have an AP selection
        if inf_count_subinterval == 0 and negative_rem_delay_subinterval == 0:
            if self.chosen_ap_ids.is_valid:
                # check if the AP selection matches with the earlier one, all SFC-s need to agree on one!
                # (which is enforced by the way AP-s are selected, here we execute a check)
                for subinterval, ap_id in self.chosen_ap_ids.items():
                    if self.chosen_ap_ids[subinterval] != current_chosen_ap_ids[subinterval]:
                        self.log.info("AP selection disagreement in subinterval {} with SFC {}: current AP {}, existing AP selection {}".
                                      format(subinterval, self.sfc_path, current_chosen_ap_ids[subinterval],
                                             self.chosen_ap_ids[subinterval]))
                        self.log.warn("Some SFC-s do not agree on the selected access points in time interval {} based on "
                                        "minimal delay, coverage obeying method! Current selection: {}, Existing selection: {}".
                                        format(subinterval, current_chosen_ap_ids, self.chosen_ap_ids.ap_selection))
            else:
                self.chosen_ap_ids.add_ap_selection_dict(current_chosen_ap_ids)

        return inf_count_subinterval, negative_rem_delay_subinterval

    def get_violating_items(self):
        """
        Returns the non-endpoint items of an SFC, if its delay or coverage probability is violated.

        :return:
        """
        violating_items = []
        inf_count_subinterval, negative_rem_delay_subinterval = self.calculate_violations()
        if inf_count_subinterval == 0 and negative_rem_delay_subinterval == 0:
            # no violations are happening for the delay OR coverage req of this SFC in any subinterval
            return violating_items
        else:
            # The allocation of this SFC is not OK, we need to move something
            for u, v in self.sfc_path:
                # the last and the first item/vnf in the SFC is an endpoint.
                v_host_id = self.id_item_map[v].mapped_to['id']
                if v_host_id not in self.infra.endpoint_ids:
                    violating_items.append(self.id_item_map[v])
        return violating_items

    def item_move_improvement_score(self, item_to_be_moved : Item, target_bin : Bin):
        """
        Identifies the item move's improvement score based on the violation metrics calculated by self.calculate_violations()

        :param item_to_be_moved:
        :param target_bin:
        :return:
        """
        improvement_score = 0
        if item_to_be_moved['id'] in self.affected_nfs:
            inf_count_subinterval_before, neg_rem_delay_subinterval_before = self.calculate_violations()

            original_bin = item_to_be_moved.mapped_to
            # Temporarily execute the item moving on the structure
            self.item_move_function(item_to_be_moved, target_bin)

            inf_count_subinterval_after, neg_rem_delay_subinterval_after = self.calculate_violations()

            if inf_count_subinterval_before == 0:
                if neg_rem_delay_subinterval_after < neg_rem_delay_subinterval_before:
                    improvement_score = 1
                elif neg_rem_delay_subinterval_after > neg_rem_delay_subinterval_before:
                    improvement_score = -1
            elif inf_count_subinterval_after < inf_count_subinterval_before:
                improvement_score = 1
            elif inf_count_subinterval_after > inf_count_subinterval_before:
                improvement_score = -1

            # undo the temporary bin move
            self.item_move_function(item_to_be_moved, original_bin)

        return improvement_score


class BatteryConstraintViolationChecker(BaseConstraintViolationChecker):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function, battery_threshold):
        super(BatteryConstraintViolationChecker, self).__init__(items, bins, infra, ns, item_move_function)
        self.battery_threshold = battery_threshold

    def get_battery_alive_prob(self, allocated_load, total_capacity):
        """
        Calculates battery alive probability according to battery constraint.
        Currently we assume all mobile nodes have the same battery characteristics.

        :param allocated_load:
        :param total_capacity:
        :return:
        """
        linear_coeff = self.infra.unloaded_battery_alive_prob - self.infra.full_loaded_battery_alive_prob
        probability = self.infra.unloaded_battery_alive_prob - allocated_load/total_capacity * linear_coeff
        # overloading might happen due to invalid capacity allocation
        if probability < 0:
            probability = 0
        # it should never go above 1.0
        if probability <= 1:
            return probability
        else:
            raise Exception("Invalid battery alive probability! Wrong battery characteristic specification?")

    def get_violating_items(self):
        """
        Checks the loads on the mobile nodes, if they are not overloaded in terms of battery usage. Returns items on overloaded in bins,
        which refer to overloaded mobile nodes.

        :return:
        """
        violating_items = []
        for bin in self.bins:
            if bin['id'] in self.infra.mobile_ids:
                if self.get_battery_alive_prob(bin.total_load, bin['capacity']) < self.battery_threshold:
                    violating_items.extend(bin.mapped_here)
        return violating_items

    def item_move_improvement_score(self, item_to_be_moved : Item, target_bin : Bin):
        """
        Prefers a move which decreases the number of violating items.

        :param item_to_be_moved:
        :param target_bin:
        :return:
        """
        violating_items_count_before = len(self.get_violating_items())
        original_bin = item_to_be_moved.mapped_to
        # temporariliy move the item to evaluate the changes
        self.item_move_function(item_to_be_moved, target_bin)
        violating_items_count_after = len(self.get_violating_items())
        # move the item back, moving decision is not to be made here.
        self.item_move_function(item_to_be_moved, original_bin)
        if violating_items_count_before > violating_items_count_after:
            return 1
        elif violating_items_count_before < violating_items_count_after:
            return -1
        else:
            return 0
