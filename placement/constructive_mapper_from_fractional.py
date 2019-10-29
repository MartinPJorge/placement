import logging
from rainbow_logging_handler import RainbowLoggingHandler
import sys
import math

from .mapper import AbstractMapper
from graphs.mapping_structure import VolatileResourcesMapping
import heuristic.placement.constraint_violation_checkers as cvc
from .support_classes import *


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
        self.infra = None
        self.ns = None
        # list of BinCapacityViolationChecker objects instantiated in the save_global_mapping_task_information fucntion
        self.violation_checkers = None
        self.hashes_of_visited_mappings = set()

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
            raise UnfeasibleVolatileResourcesProblem("None of the bins can host the smallest item!")
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
            raise UnfeasibleVolatileResourcesProblem("Total item weight {} is more than all the bin capacities {}".
                                                     format(self.total_item_weight, total_bin_capacity))

    def map_all_items_to_bins(self, best_bins):
        """
        Round the fractional optimal solution defined by the best_bins.
        Round the x_ij mapping variable to the highest one, aka, get the highest capacity bin from the
        intersection of the possible bins of an item and the input best bins
        Preference is set only for the best_bins, not all bins in the self.bins!
        Ignores all other constrains from infra and ns

        :param best_bins:
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
                raise UnfeasibleVolatileResourcesProblem("Item {} cannot be mapped anywhere".format(item))

    @staticmethod
    def move_item_to_bin(item_to_be_moved, target_bin):
        # delete the mapping of the foudn item from its current mapping
        if item_to_be_moved not in item_to_be_moved.mapped_to.mapped_here:
            raise Exception("Item is not found in mapped_to of a bin where it should have been!")
        item_to_be_moved.mapped_to.mapped_here.remove(item_to_be_moved)
        target_bin.mapped_here.append(item_to_be_moved)
        # set its mapping to the target bin
        item_to_be_moved.mapped_to = target_bin

    def hash_of_current_mapping(self):
        """
        Creates a hashable structure which identifies the current mapping, and returns its hash

        :return:
        """
        bins_items = list()
        for bin in self.bins:
            bins_items.append(frozenset(bin.mapped_here))
        return hash(tuple(bins_items))

    def hash_of_mapping_after_item_move(self, item_to_be_moved, target_bin):
        """
        Calculates the hash of a mapping after the item is moved to the target bin

        :param item_to_be_moved:
        :param target_bin:
        :return:
        """
        original_bin = item_to_be_moved.mapped_to
        ConstructiveMapperFromFractional.move_item_to_bin(item_to_be_moved, target_bin)
        mapping_hash = self.hash_of_current_mapping()
        ConstructiveMapperFromFractional.move_item_to_bin(item_to_be_moved, original_bin)
        return mapping_hash

    def improve_item_to_bin_mappings(self, best_bins):
        """
        Moves the item, which increases the objective the least, to one of the best bins where it fits.

        :param best_bins: moving target can only be to these bins
        :return: bool tuple, whether there is anything left to improve; whether more improvement is needed
        """
        violating_items = set()
        improvement_score_stats = dict()
        key_gen = lambda checker: checker.__class__.__name__+str(int(id(checker)))
        for checker in self.violation_checkers:
            violating_items = violating_items.union(checker.get_violating_items())
            improvement_score_stats[key_gen(checker)] = []
        if len(violating_items) == 0:
            # if the delay violation checker didn't return violating items either, then it must have calculated a complete AP selection!
            # (not the nicest way to communicate this information...)
            if cvc.DelayAndCoverageViolationChecker.calculate_current_ap_selection_cost(self.infra) is None:
                raise Exception("If no violations are found by any ViolationChecker, a complete AP selection must exist!")
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
                    # it might happen that this goes on for a long time, and many improvement steps fail due to not having possible bins
                    # in the best bins. If this is the case, we choose the next best bins from these possible bins.
                    current_possible_bins_needed.extend(item.possible_bins)
                    unmovable_violating_items.append(item)
                    continue
                for bin in best_bins:
                    if bin is not item.mapped_to and bin in item.possible_bins:
                        if self.hash_of_mapping_after_item_move(item, bin) in self.hashes_of_visited_mappings:
                            # self.log.debug("Skipping moving item {} to bin {} as we have already visited this mapping".format(item, bin))
                            continue
                        total_item_move_improvement_score = 0
                        for checker in self.violation_checkers:
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
                            cost_of_improvement = bin.get_variable_cost_of_mapping(item) - \
                                                  item.mapped_to.get_variable_cost_of_mapping(item)
                            # we cannot include the improvement on the total AP selection cost, because with the heuristic, a mapping
                            # setting must unambiguously identify the AP selection.
                            # see "# NOTE" in DelayAndCoverageViolationChecker.calculate_violations
                            # TODO: work out a way to include improvement on AP selection cost?? (difficult, not fit well to the current design)
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
                # If no improvement score calculations happened, and there is an unmoveable item,
                # let's introduce bins from its possible_bins
                self.log.debug("Saving next bins for unmovable violating items: {}".format(unmovable_violating_items))
                # self.possible_bins_needed stores the bins required
                self.possible_bins_needed = current_possible_bins_needed

                # if a target bin is set we can execute the moving
            if target_bin is not None:
                self.log.debug("Improving mapping by moving item {} to target bin {}".
                               format(item_to_be_moved, target_bin))
                ConstructiveMapperFromFractional.move_item_to_bin(item_to_be_moved, target_bin)
                self.hashes_of_visited_mappings.add(self.hash_of_current_mapping())
                # NOTE: even if this is the very last improvement, it will turn out in the next call of this function
                return True, True
            else:
                return False, True

    def get_new_best_bins(self, best_bins) -> tuple:
        """
        Returns the new list of the best bins (moving/adding possible),
        and bool to indicate wether we can add another bin if necessary.
        This implementation always only adds the next bin according to their filled unit cost.

        :param best_bins:
        :return:
        """
        if self.check_all_constraints_calculate_objective(self.infra):
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

    def check_all_constraints_calculate_objective(self, infra):
        """
        Checks if the constructed solution for the bin packing is valid.
        Also calculates the objective_value_of_integer_solution if the solution is valid.
        Checks other constraints not only the pure bin packing problem's capacity constraints.

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
        # check if we have a complete allocation for the APs (which implies meeting the delay and coverage constraints)
        total_ap_selection_cost = cvc.DelayAndCoverageViolationChecker.calculate_current_ap_selection_cost(infra)
        if total_ap_selection_cost is None:
            self.objective_value_of_integer_solution = None
            return False
        else:
            self.log.debug("Total cost of access point selections: {}".format(total_ap_selection_cost))
            self.objective_value_of_integer_solution += total_ap_selection_cost
        # easiest is to instantiate a new checker and run its violation checker
        battery_checker = cvc.BatteryConstraintViolationChecker(self.items, self.bins, self.infra, self.ns,
                                                                ConstructiveMapperFromFractional.move_item_to_bin,
                                                                self.battery_threshold)
        if len(battery_checker.get_violating_items()) > 0:
            return False
        return True

    def construct_output_mapping(self, mapping : VolatileResourcesMapping):
        """
        Constructs an output mapping object

        :param mapping:
        :return:
        """
        mapping['worked'] = True
        mapping[mapping.OBJECTIVE_VALUE] = self.objective_value_of_integer_solution
        for i in self.items:
            mapping[i['node_dict'][self.ns.node_name_str]] = i.mapped_to['node_dict'][self.infra.node_name_str]
        for subinterval, ap_id in cvc.DelayAndCoverageViolationChecker.chosen_ap_ids.items():
            mapping.add_access_point_selection(subinterval, self.infra.nodes[ap_id][self.infra.node_name_str])

        return mapping

    def save_global_mapping_task_information(self, infra : InfrastructureGMLGraph, ns : ServiceGMLGraph):
        """
        The AbstractMapper interface the constructor does not receive the infra and ns instances, but they are constant during the
        algorithm, so we can save it to the instance.
        # TODO (refactor): remove infra and ns from the function step interfaces, they are the same objects as self.infra and self.ns...

        :param infra:
        :param ns:
        :return:
        """
        self.infra = infra
        self.ns = ns

    def instantiate_violation_checkers(self):
        """
        Creates violation checkers for all constraints considered by the heuristic algorithm.

        :return:
        """
        self.violation_checkers = [cvc.BinCapacityViolationChecker(self.items, self.bins, self.infra, self.ns,
                                                                   ConstructiveMapperFromFractional.move_item_to_bin),
                                   cvc.BatteryConstraintViolationChecker(self.items, self.bins, self.infra, self.ns,
                                                                         ConstructiveMapperFromFractional.move_item_to_bin,
                                                                         self.battery_threshold)]
        # add a separate checker for each SFC
        for sfc_delay, sfc_path in self.ns.sfc_delays_list:
            self.violation_checkers.append(cvc.DelayAndCoverageViolationChecker(self.items, self.bins, self.infra, self.ns,
                                                                                ConstructiveMapperFromFractional.move_item_to_bin,
                                                                                sfc_delay, sfc_path, self.time_interval_count,
                                                                                self.coverage_threshold))

    def map(self, infra, ns) -> dict:
        mapping = VolatileResourcesMapping()
        # Check that graphs have correct format
        if not self.__checker.check_infra(infra) or not self.__checker.check_ns(ns):
            return mapping

        self.save_global_mapping_task_information(infra, ns)
        self.get_base_bin_packing_problem(infra, ns)
        self.instantiate_violation_checkers()
        for pruning in self.pruning_steps_collection:
            self.items, self.bins = pruning.prune_possible_mappings(infra, ns, self.items, self.bins)

        # get fractional solution: it is completely defined by listing the first 'k' bins according to
        # the definition of the paper in section 2.1.
        # NOTE: 'k' = len(best_bins)
        try:
            best_bins = self.get_fist_best_bins()
            # get rounding : map all items somewhere, not neccessarily respecting the constraints.
            # NOTE: With another heuristic it might be needed to be run again, after a new bin is introduced.
            self.map_all_items_to_bins(best_bins)
            can_add_next_bin = True
            while can_add_next_bin:
                anything_left_to_improve = True
                any_violation_left = True
                while anything_left_to_improve:
                    # get mapping improvement : improve on the item mappings
                    anything_left_to_improve, any_violation_left = self.improve_item_to_bin_mappings(best_bins)
                if not any_violation_left:
                    break
                # get new bin : if there is nothing left to improve with the current bins, we can introduce new ones
                best_bins, can_add_next_bin = self.get_new_best_bins(best_bins)
        except UnfeasibleVolatileResourcesProblem as ubp:
            self.log.info(ubp.msg)
            return mapping

        if not self.check_all_constraints_calculate_objective(infra):
            self.log.info("Bin packing solution not found by the heuristic!")
            return mapping
        else:
            self.log.info("Bin packing solution found with objective value {}, while fractional optimal value is {}".
                          format(self.objective_value_of_integer_solution, self.objective_value_of_fractional_opt))
            mapping = self.construct_output_mapping(mapping)
            if not mapping.validate_mapping(ns, infra,
                                            self.time_interval_count, self.coverage_threshold, self.battery_threshold):
                self.log.error("Heuristic algorithm solution does not respect some constraint!")
                raise Exception("Heuristic algorithm solution does not respect some constraint!")
            else:
                self.log.info("Mapping solution validation is successful!")
            return mapping

