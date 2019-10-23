from abc import ABCMeta, abstractmethod
import logging
from rainbow_logging_handler import RainbowLoggingHandler
import sys
import math

from .mapper import AbstractMapper
from .checker import AbstractChecker
from graphs.generate_service import ServiceGMLGraph, InfrastructureGMLGraph
from graphs.mapping_structure import VolatileResourcesMapping


class UnfeasibleBinPacking(Exception):

    def __init__(self, msg, *args, **kwargs):
        super(UnfeasibleBinPacking, self).__init__(*args, **kwargs)
        self.msg = msg


class VolatileResourcesChecker(AbstractChecker):

    def __init__(self):
        super(VolatileResourcesChecker, self).__init__()

    def check_infra(self, infra) -> bool:
        """


        :param infra:
        :type infra: simulator.generate_service.InfrastructureGMLGraph
        :return:
        """
        return infra.check_graph()

    def check_ns(self, ns) -> bool:
        """


        :param ns:
        :type ns: simulator.generate_service.ServiceGMLGraph
        :return:
        """
        return ns.check_graph()


class Item(dict):

    def __init__(self, id, weight, node_dict, possible_bins, seq=None, mapped_to = None, **kwargs):
        """
        Class to store information about an item of the bin packing problem.
        The mapped_to key represents the Bin object bin where this is mapped, None by default.

        :param weight:  weight to be used for placement
        :param node_dict: dictionary of the correspoinding VNF read from the input
        :param seq:
        :param possible_bins: list of Bin objects where this item might possibly go.
        :param kwargs:
        """
        super(Item, self).__init__(seq=seq, id=id, node_dict=node_dict, weight=weight, **kwargs)
        self.mapped_to = mapped_to
        self.possible_bins = possible_bins

    def __repr__(self):
        return "Item(id={}, weight={}, mapped_to={})".format(self['id'], self['weight'], self.mapped_to)

    def __hash__(self):
        # ID uniquely defines the Item, it is ensured by the NetworkX graph
        return hash(str(self['id']))


class Bin(dict):

    def __init__(self, id, capacity, fixed_cost, unit_cost, node_dict, mapped_here, seq=None, **kwargs):
        """
        Class to store and calculate info for a bin of the bin packing problem.
        The mapped_here attribute stores the items mapped here.

        :param id:
        :param capacity:
        :param fixed_cost:
        :param unit_cost:
        :param node_dict:
        :param seq:
        :param kwargs:
        """
        super(Bin, self).__init__(seq=seq, id=id, capacity=capacity, fixed_cost=fixed_cost,
                                  unit_cost=unit_cost, node_dict=node_dict, **kwargs)
        self.mapped_here = mapped_here
        self.preference = None

    @property
    def filled_unit_cost(self):
        if self['capacity'] > 0:
            fixed_part = self['fixed_cost'] / self['capacity']
        else:
            fixed_part = float('inf')
        return fixed_part + self['unit_cost']

    @property
    def total_load(self):
        return sum(map(lambda i: i['weight'], self.mapped_here))

    @property
    def is_overloaded(self):
        return self['capacity'] < self.total_load

    def does_item_fit(self, item):
        return self['capacity'] >= self.total_load + item['weight']

    def get_variable_cost_of_mapping(self, item):
        return item['weight'] * self['unit_cost']

    def __repr__(self):
        return "Bin(id={}, capacity={})".format(self['id'], self['capacity'])


class BasePruningStep(metaclass=ABCMeta):

    def __init__(self):
        super(BasePruningStep, self).__init__()

    @abstractmethod
    def prune_possible_mappings(self, infra, ns, items : list, bins : list) -> tuple:
        """
        The result of the pruning must be relfected in the Item.possible_bins attribute of the results

        :param infra:
        :param ns:
        :param items: list of Items
        :param bins: list of Bins
        :return: tuple of the pruned items and bins
        """
        pass


class PruneLocalityConstraints(BasePruningStep):

    def prune_possible_mappings(self, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, items : list, bins : list):
        """
        Remove possible bins which contradict the locality constraints stored in the VNF/their corresponding Item.

        :param infra:
        :param ns:
        :param items:
        :param bins:
        :return:
        """
        for item in items:
            if ns.location_constr_str in item['node_dict']:
                # we need to make a list from the bins, otherwise we couldnt remove from it
                for bin in list(item.possible_bins):
                    if bin['id'] not in item['node_dict'][ns.location_constr_str]:
                        item.possible_bins.remove(bin)
        return items, bins


class BaseConstraintViolationChecker(metaclass=ABCMeta):

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph):
        super(BaseConstraintViolationChecker, self).__init__()
        self.bins = bins
        self.items = items
        self.ns = ns
        self.infra = infra
        self.violating_items = None
        self.id_item_map = {i['id'] : i for i in self.items}

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

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph):
        super(BinCapacityViolationChecker, self).__init__(items, bins, infra, ns)

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

    def __init__(self, items, bins, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph, sfc_delay, sfc_path,
                 time_interval_count, coverage_threshold):
        super(DelayAndCoverageViolationChecker, self).__init__(items, bins, infra, ns)
        self.sfc_delay = sfc_delay
        self.sfc_path = sfc_path
        self.affected_nfs = [v for u,v in self.sfc_path]
        self.coverage_threshold = coverage_threshold
        self.time_interval_count = time_interval_count

    def calculate_violations(self):
        """
        Calculates the number of violating time intervals in the current allocation, respecting the coverage probability,
        described by a tuple:
            (number of subintervals, where the SFC delay is infinite;
            number of subintervals, where remaining SFC delay is negative)
        Second number is only informative, if the first number is 0.

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
        for subinterval in range(1, self.time_interval_count+1):
            rem_delay_in_subint = remaining_delay
            for u, v in self.sfc_path:
                u_host_id = self.id_item_map[u].mapped_to['id']
                v_host_id = self.id_item_map[v].mapped_to['id']
                # filter for links mapped over the wireless channel
                if (u_host_id in all_mobile_node_ids and v_host_id in all_fixed_node_ids) or \
                        (u_host_id in all_fixed_node_ids and v_host_id in all_mobile_node_ids):
                    # find the best possible delay, which obeys the coverage probabilty through ANY access point.
                    min_wireless_delay_with_cov = float('inf')
                    min_delay_though_ap_id = None
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


        :param item_to_be_moved:
        :param target_bin:
        :return:
        """
        improvement_score = 0
        if item_to_be_moved['id'] in self.affected_nfs:
            inf_count_subinterval_before, neg_rem_delay_subinterval_before = self.calculate_violations()

            original_bin = item_to_be_moved.mapped_to
            # Temporarily execute the item moving on the structure
            ConstructiveMapperFromFractional.move_item_to_bin(item_to_be_moved, target_bin)

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
            ConstructiveMapperFromFractional.move_item_to_bin(item_to_be_moved, original_bin)

        return improvement_score


class ConstructiveMapperFromFractional(AbstractMapper):

    def __init__(self, checker: AbstractChecker, coverage_threshold, time_interval_count, battery_threshold, log=None, improvement_score_limit=1):
        """
        Constructs a solution for the volatile resources problem based on the fractional optimal solution
        for the inherent bin packing problem as defined by Cambazard, et. al. -- Bin Packing with Linear Usage
        Costs - An Application to Energy Management in Data Centres, https://hal.archives-ouvertes.fr/hal-00858159

        :param checker:
        """
        super(ConstructiveMapperFromFractional, self).__init__(checker)
        # NOTE: names starting with __ are sort of private methods in python
        self.__checker = checker
        self.bins = []
        self.items = []
        self.pruning_steps_collection = [PruneLocalityConstraints()]
        self.objective_value_of_fractional_opt = None
        self.objective_value_of_integer_solution = None
        if log is None:
            self.log = logging.Logger(self.__class__.__name__)
            handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
            formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
            handler.setFormatter(formatter)
            self.log.addHandler(handler)
            self.log.setLevel(logging.INFO)
        else:
            self.log = log.getChild(self.__class__.__name__)
            for handler in log.handlers:
                self.log.addHandler(handler)
            self.log.setLevel(log.getEffectiveLevel())

        # these might not be needed if we override the functions with other heuristics.
        self.epsilon = 1e-3
        self.min_bin_preference = None
        self.improvement_score_limit = improvement_score_limit
        # compulsory parameters
        self.time_interval_count = time_interval_count
        self.battery_threshold = battery_threshold
        self.coverage_threshold = coverage_threshold
        # variable to communicate between the new best bins and the item move improvement step functions
        self.possible_bins_needed = []

    @property
    def total_item_weight(self):
         return sum(map(lambda i: i['weight'], self.items))

    def get_bins_sorted_by_filled_unit_cost(self):
        return sorted(self.bins, key=lambda b: b.filled_unit_cost)

    def get_base_bin_packing_problem(self, infra, ns):
        """
        Constructs a base binpacking problem without filtering out any of the possible mappings.

        :param infra:
        :param ns:
        :return:
        """
        for n, node_dict in ns.nodes(data=True):
            # TODO: fill in from values of the node based on checker.
            # TODO (we might filter out APs and endpoints here already -- If we know what exactly will be their 'type' fields)
            # initialize the problem with all possible bins
            self.items.append(Item(n, node_dict[ns.nf_demand_str], node_dict, possible_bins=[]))
        min_weighted_item = min(self.items, key=lambda i: i['weight'])
        for n, node_dict in infra.nodes(data=True):
            # TODO: fill in from values of the node based on checker.
            bin = Bin(n, node_dict[infra.infra_node_capacity_str], node_dict[infra.infra_fixed_cost_str],
                      node_dict[infra.infra_unit_cost_str], node_dict, mapped_here=[])
            if bin['capacity'] >= min_weighted_item['weight']:
                self.bins.append(bin)
            elif bin['capacity'] > self.epsilon:
                # items and bins with 0 capacity might appear as access points
                self.log.info("Discarding bin {} because it cannot fit even the smallest item".format(bin))
        if len(self.bins) == 0:
            raise UnfeasibleBinPacking("None of the bins can host the smallest item!")
        # set possible bins for all items (discard ones with insufficient capacity)
        for item in self.items:
            # important to have a separate list for the possible bins for each item
            # (removing from one, Must not be reflected in another item's possible bins)
            item.possible_bins.extend([b for b in self.bins if b['capacity'] >= item['weight']])

    def set_initial_bin_preferences(self, original_best_bins, total_bin_capacity):
        # sets the preference to the same ordering which is given by the fractional mapping variables for the best bins as defined
        # in the referenced paper (originally the x_ij values has a denominator, but this does not influence their rounding, so it
        # is ommited).
        self.objective_value_of_fractional_opt = 0.0
        for bin in original_best_bins:
            if bin is original_best_bins[-1]:
                # the last item has less preference than its capacity
                bin.preference = self.total_item_weight - (total_bin_capacity - bin['capacity'])
            else:
                bin.preference = bin['capacity']
            self.objective_value_of_fractional_opt += bin['fixed_cost'] + bin.preference * bin['unit_cost']

    def get_fist_best_bins(self):
        """
        Gets the first 'k' best bins according to the paper's definition in section 2.1.
        This fully defines the fractional optimal solution.

        :return: sorted best bins
        """
        sorted_bins = self.get_bins_sorted_by_filled_unit_cost()
        total_bin_capacity = 0.0
        best_bins = []
        for bin in sorted_bins:
            total_bin_capacity += bin['capacity']
            best_bins.append(bin)
            if total_bin_capacity >= self.total_item_weight:
                self.set_initial_bin_preferences(best_bins, total_bin_capacity)
                return best_bins
        else:
            raise UnfeasibleBinPacking("Total item weight {} is more than all the bin capacities {}".
                                       format(self.total_item_weight, total_bin_capacity))

    def map_all_items_to_bins(self, best_bins, infra, ns):
        """
        Round the fractional optimal solution defined by the best_bins.
        Round the x_ij mapping variable to the highest one, aka, get the highest capacity bin from the
        intersection of the possible bins of an item and the input best bins
        Preference is set only for the best_bins, not all bins in the self.bins!
        Ignores all other constrains from infra and ns

        :param best_bins:
        :param infra:
        :param ns:
        :return:
        """
        for item in self.items:
            best_and_possible_bins = [b for b in best_bins if b in item.possible_bins]
            if len(best_and_possible_bins) > 0:
                # preference is only set for the initial 'k' best_bins, if we need to introduce new bins to get a constraint
                # non-violating solution, we introduce them according to their filled unit cost as they give the cheapest solution.
                chosen_bin = max(best_and_possible_bins, key=lambda b: b.preference)
                item.mapped_to = chosen_bin
                chosen_bin.mapped_here.append(item)
            elif len(item.possible_bins) == 1:
                item.mapped_to = item.possible_bins[0]
                item.possible_bins[0].mapped_here.append(item)
            elif len(item.possible_bins) > 1:
                # It happens when there is no intersection of the best bins and the possible bins.
                self.log.info("Setting initial mapping for item {} to be the cheapest of its possible bins, as it cannot be mapped "
                              "to initially chosen bins.".format(item))
                # choose the cheapest bin among the possible ones (natural extension of the algorithm).
                for bin in self.get_bins_sorted_by_filled_unit_cost():
                    if bin in item.possible_bins:
                        item.mapped_to = bin
                        bin.mapped_here.append(item)
                        break
            else:
                raise UnfeasibleBinPacking("Item {} cannot be mapped anywhere".format(item))

    @staticmethod
    def move_item_to_bin(item_to_be_moved, target_bin):
        # delete the mapping of the foudn item from its current mapping
        if item_to_be_moved not in item_to_be_moved.mapped_to.mapped_here:
            raise Exception("Item is not found in mapped_to of a bin where it should have been!")
        item_to_be_moved.mapped_to.mapped_here.remove(item_to_be_moved)
        target_bin.mapped_here.append(item_to_be_moved)
        # set its mapping to the target bin
        item_to_be_moved.mapped_to = target_bin

    def improve_item_to_bin_mappings(self, best_bins, infra, ns):
        """
        Moves the item, which increases the objective the least, to one of the best bins where it fits.

        :param best_bins: moving target can only be to these bins
        :param infra:
        :param ns:
        :return: bool tuple, whether there is anything left to improve; whether more improvement is needed
        """
        # NOTE: violation checkers are only in a local scope, but some refactor could be done, to instantiate them at the constructor.
        violation_checkers = [BinCapacityViolationChecker(self.items, self.bins, infra, ns)]
        # add a separate checker for each SFC
        for sfc_delay, sfc_path in ns.sfc_delays_list:
            violation_checkers.append(DelayAndCoverageViolationChecker(self.items, self.bins, infra, ns, sfc_delay, sfc_path,
                                                                       self.time_interval_count, self.coverage_threshold))
        violating_items = set()
        improvement_score_stats = dict()
        key_gen = lambda checker: checker.__class__.__name__+str(int(hash(checker)/10000000000))
        for checker in violation_checkers:
            violating_items = violating_items.union(checker.get_violating_items())
            improvement_score_stats[key_gen(checker)] = []
        if len(violating_items) == 0:
            return False, False
        else:
            cost_of_cheapest_improvement = float('inf')
            target_bin = None
            item_to_be_moved = None
            improvement_score_stats['total'] = []
            current_possible_bins_needed = []
            unmovable_violating_items = []
            for item in violating_items:
                if not any(b in item.possible_bins for b in best_bins):
                    self.log.debug("Violating item {} cannot be moved to any of the current best bins due to its possible bins list".format(item))
                    # TODO: it might happen that this goes on for a long time, and many improvement steps fail due to not having possible bins in the best bins. If this is the case, maybe we could choose the next best bins from these possible bins.
                    current_possible_bins_needed.extend(item.possible_bins)
                    unmovable_violating_items.append(item)
                    continue
                for bin in best_bins:
                    if bin is not item.mapped_to and bin in item.possible_bins:
                        total_item_move_improvement_score = 0
                        for checker in violation_checkers:
                            improvement_score = checker.item_move_improvement_score(item, bin)
                            total_item_move_improvement_score += improvement_score
                            improvement_score_stats[key_gen(checker)].append(improvement_score)
                        improvement_score_stats['total'].append(total_item_move_improvement_score)
                        if total_item_move_improvement_score >= self.improvement_score_limit:
                            # might be useful later, for now it is too many log entries
                            # self.log.debug("Total item move improvement score: {} >= {} for moving {} to {}".
                            #                 format(total_item_move_improvement_score, self.improvement_score_limit, item, bin))
                            # Difference between the current mapping and the possible relocation.
                            # This value might be even negative, if the rounding did not consider taking the first fitting bin in the
                            # ordered best bin list.
                            # TODO: include AP usage cost!!
                            cost_of_improvement = bin.get_variable_cost_of_mapping(item) - \
                                                  item.mapped_to.get_variable_cost_of_mapping(item)
                            if cost_of_improvement < cost_of_cheapest_improvement:
                                cost_of_cheapest_improvement = cost_of_improvement
                                target_bin = bin
                                item_to_be_moved = item
            if len(improvement_score_stats['total']) != 0:
                self.log.debug("Improvement score averages: {}".format(
                    {k : ("{0:.4f}".format(math.fsum(v)/len(v)) if len(v) > 0 else "N/A") for k, v in improvement_score_stats.items()}))
                # if there are improvements, do not interfere with the algorithm
                self.possible_bins_needed = []
            elif len(unmovable_violating_items) > 0:
                self.log.debug("Saving next bins for unmovable violating items: {}".format(unmovable_violating_items))
                # self.possible_bins_needed stores the bins required
                self.possible_bins_needed = current_possible_bins_needed

                # if a target bin is set we can execute the moving
            if target_bin is not None:
                self.log.debug("Improving mapping by moving item {} to target bin {}".
                               format(item_to_be_moved, target_bin))
                ConstructiveMapperFromFractional.move_item_to_bin(item_to_be_moved, target_bin)
                # NOTE: even if this is the very last improvement, it will turn out in the next call of this function
                return True, True
            else:
                return False, True

    def get_new_best_bins(self, best_bins, infra, ns) -> tuple:
        """
        Returns the new list of the best bins (moving/adding possible),
        and bool to indicate wether we can add another bin if necessary.
        This implementation always only adds the next bin according to their filled unit cost.

        :param best_bins:
        :param infra:
        :param ns:
        :return:
        """
        if self.check_bin_mapping():
            # we dont have to add next bin, everything is mapped to the current best bins
            return best_bins, False
        else:
            force_bin_choosing = False
            if len(self.possible_bins_needed) > 0:
                force_bin_choosing = True
                self.log.debug("Forcing next bin selection to choose from the required possible bins (examples): {}".format(self.possible_bins_needed[:5]))
            for bin in self.get_bins_sorted_by_filled_unit_cost():
                if bin not in best_bins:
                    if force_bin_choosing and bin not in self.possible_bins_needed:
                        # we need to skip this bin for now, it is more urgent to choose a bin, which is required anyway
                        continue
                    best_bins.append(bin)
                    self.log.info("Introducing next new bin {}".format(bin))
                    # we return with the first one right away
                    return best_bins, True
            else:
                # it means, that all bins are already in the best bins.
                return best_bins, False

    def check_bin_mapping(self):
        """
        Checks if the constructed solution for the bin packing is valid.
        Also calculates the objective_value_of_integer_solution if the solution is valid.

        :return:
        """
        self.objective_value_of_integer_solution = 0.0
        for item in self.items:
            if item.mapped_to is None:
                self.objective_value_of_integer_solution = None
                return False
            else:
                self.objective_value_of_integer_solution += item.mapped_to.get_variable_cost_of_mapping(item)
        all_items = list(self.items)
        for bin in self.bins:
            if bin.is_overloaded:
                self.objective_value_of_integer_solution = None
                return False
            elif len(bin.mapped_here) > 0:
                for item in bin.mapped_here:
                    if item in all_items:
                        all_items.remove(item)
                    else:
                        raise Exception("Wrong item mapping structure, each item must be in exactly one bin!")
                self.objective_value_of_integer_solution += bin['fixed_cost']
        if len(all_items) != 0:
            raise Exception("Item not found in mapped_here structure in any bin!")
        return True

    def construct_output_mapping(self, mapping, ns : ServiceGMLGraph, infra : InfrastructureGMLGraph):
        """
        Constructs an output mapping object

        :param mapping:
        :return:
        """
        mapping['worked'] = True
        for i in self.items:
            mapping[i['node_dict'][ns.node_name_str]] = i.mapped_to['node_dict'][infra.node_name_str]

        return mapping

    def map(self, infra, ns) -> dict:
        mapping = VolatileResourcesMapping()
        # Check that graphs have correct format
        if not self.__checker.check_infra(infra) or not self.__checker.check_ns(ns):
            return mapping

        self.get_base_bin_packing_problem(infra, ns)
        for pruning in self.pruning_steps_collection:
            self.items, self.bins = pruning.prune_possible_mappings(infra, ns, self.items, self.bins)

        # get fractional solution: it is completely defined by listing the first 'k' bins according to
        # the definition of the paper in section 2.1.
        # NOTE: 'k' = len(best_bins)
        try:
            best_bins = self.get_fist_best_bins()
            # get rounding : map all items somewhere, not neccessarily respecting the constraints.
            # NOTE: With another heuristic it might be needed to be run again, after a new bin is introduced.
            self.map_all_items_to_bins(best_bins, infra, ns)
            can_add_next_bin = True
            while can_add_next_bin:
                anything_left_to_improve = True
                any_violation_left = True
                while anything_left_to_improve:
                    # get mapping improvement : improve on the item mappings
                    anything_left_to_improve, any_violation_left = self.improve_item_to_bin_mappings(best_bins, infra, ns)
                if not any_violation_left:
                    break
                # get new bin : if there is nothing left to improve with the current bins, we can introduce new ones
                best_bins, can_add_next_bin = self.get_new_best_bins(best_bins, infra, ns)
        except UnfeasibleBinPacking as ubp:
            self.log.exception(ubp.msg)
            raise ubp
            # TODO: for development keep it raised!
            # mapping['worked'] = False
            # return mapping

        if not self.check_bin_mapping():
            self.log.info("Bin packing solution not found by the heuristic!")
            return mapping
        else:
            self.log.info("Bin packing solution found with objective value {}, while fractional optimal value is {}".
                          format(self.objective_value_of_integer_solution, self.objective_value_of_fractional_opt))
            mapping = self.construct_output_mapping(mapping, ns, infra)
            if not mapping.validate_mapping(ns, infra):
                self.log.error("Heuristic algorithm solution does not respect some constraint!")
                raise Exception("Heuristic algorithm solution does not respect some constraint!")
            else:
                self.log.info("Mapping solution validation is successful!")
            return mapping

