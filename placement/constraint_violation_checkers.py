from .support_classes import *


class BaseConstraintViolationChecker(metaclass=ABCMeta):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function):
        super(BaseConstraintViolationChecker, self).__init__()
        self.bins = bins
        self.items = items
        self.ns = ns
        self.infra = infra
        self.violating_items = None
        self.id_item_map = {i['id'] : i for i in self.items}
        # function which executes an item move in the (global) bin mapping structure
        self.item_move_function = item_move_function

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

    # stores the AP id for each time interval which, has the lowest delay, obeying the coverage probability
    # The variable needs to be class level, because the AP selection must agree for all SFC-s. It is set to None
    chosen_ap_ids = None

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function, sfc_delay, sfc_path,
                 time_interval_count, coverage_threshold):
        super(DelayAndCoverageViolationChecker, self).__init__(items, bins, infra, ns, item_move_function)
        self.sfc_delay = sfc_delay
        self.sfc_path = sfc_path
        self.affected_nfs = [v for u,v in self.sfc_path]
        self.coverage_threshold = coverage_threshold
        self.time_interval_count = time_interval_count

    def get_cheapest_ap_id(self, subinterval):
        master_mobile_id = list(self.infra.ap_coverage_probabilities.keys())[0]
        # choose the cheapest AP which meets the coverage threshold
        min_ap_cost = float('inf')
        min_cost_ap_id = None
        for ap_id, coverage_prob in self.infra.ap_coverage_probabilities[master_mobile_id][subinterval].items():
            if coverage_prob > self.coverage_threshold:
                ap_cost = self.infra.nodes[ap_id][self.infra.access_point_usage_cost_str]
                if ap_cost < min_ap_cost:
                    min_ap_cost = ap_cost
                    min_cost_ap_id = ap_id
        if min_cost_ap_id is not None:
            return min_cost_ap_id
        else:
            raise UnfeasibleVolatileResourcesProblem("No access point found for the cluster with the given coverage probability, "
                                                     "even without checking the delay requirements!")

    def calculate_violations(self):
        """
        Calculates the number of violating time intervals in the current allocation, respecting the coverage probability,
        described by a tuple:
            (number of subintervals, where the SFC delay is infinite;
            number of subintervals, where remaining SFC delay is negative)
        Second number is only informative, if the first number is 0.
        Updates the DelayAndCoverageViolationChecker.chosen_ap_ids dictionary to reflect the violation metrics returned by the function.

        :return: int tuple
        """
        remaining_delay = float(self.sfc_delay)
        all_mobile_node_ids = self.infra.cluster_endpoint_ids + self.infra.mobile_ids
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

        inf_count_subinterval = 0
        negative_rem_delay_subinterval = 0
        # stores the AP id for each time interval which, has the lowest delay, obeying the coverage probability
        chosen_ap_ids = dict()
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
                    # and save it in a static class variable
                    min_wireless_delay_with_cov = float('inf')
                    for ap_id in self.infra.access_point_ids:
                        curr_wireless_delay_with_cov = self.infra.delay_distance(u_host_id, v_host_id, subinterval,
                                                                                 self.coverage_threshold, ap_id)
                        if curr_wireless_delay_with_cov < min_wireless_delay_with_cov:
                            min_wireless_delay_with_cov = curr_wireless_delay_with_cov
                            min_delay_though_ap_id = ap_id
                    # evaluate the situation for the output numbers
                    if min_wireless_delay_with_cov == float('inf'):
                        inf_count_subinterval += 1
                    elif rem_delay_in_subint < min_wireless_delay_with_cov:
                        negative_rem_delay_subinterval += 1
                    else:
                        rem_delay_in_subint -= min_wireless_delay_with_cov
            if inf_count_subinterval == 0 and negative_rem_delay_subinterval == 0:
                if min_delay_though_ap_id is not None:
                    chosen_ap_ids[subinterval] = min_delay_though_ap_id
                elif remaining_delay == rem_delay_in_subint:
                    # if all nodes are mapped inside the cluster or inside the fixed infra part, we
                    chosen_ap_ids[subinterval] = self.get_cheapest_ap_id(subinterval)
                else:
                    raise Exception("AP must always be selected if the delay and coverage are OK in a mapping!")
            else:
                DelayAndCoverageViolationChecker.chosen_ap_ids = None

        # if the delay and coverage values are violated in none of the subintervals, then we have an AP selection
        if inf_count_subinterval == 0 and negative_rem_delay_subinterval == 0:
            DelayAndCoverageViolationChecker.chosen_ap_ids = chosen_ap_ids

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

    @staticmethod
    def calculate_current_ap_selection_cost(infra : InfrastructureGMLGraph):
        """
        Sums the cost of the currently selected AP-s if the last calculated constraint violation function found a coverage and delay
        respecting allocation for all subintervals.

        :param infra:
        :return:
        """
        total_ap_cost = None
        if DelayAndCoverageViolationChecker.chosen_ap_ids is not None:
            total_ap_cost = 0.0
            for subinterval, selected_ap_id in DelayAndCoverageViolationChecker.chosen_ap_ids.items():
                # MAYBE: divide by the number of time intervals as the meaning of an AP cost is to use that for the whole interval
                # (similarly to the cost of a vCPU for the whole interval)
                # BUT then we need to modify the AMPL model objective function too for reasonable comparison!!!!
                total_ap_cost += infra.nodes[selected_ap_id][infra.access_point_usage_cost_str]
        return total_ap_cost


class BatteryConstraintViolationChecker(BaseConstraintViolationChecker):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, item_move_function):
        super(BatteryConstraintViolationChecker, self).__init__(items, bins, infra, ns, item_move_function)

    def get_violating_items(self):
        pass

    def item_move_improvement_score(self, item_to_be_moved : Item, target_bin : Bin):
        pass
