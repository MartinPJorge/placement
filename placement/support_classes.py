from graphs.generate_service import ServiceGMLGraph, InfrastructureGMLGraph
from .checker import AbstractChecker
from abc import ABCMeta, abstractmethod


class UnfeasibleVolatileResourcesProblem(Exception):

    def __init__(self, msg, *args, **kwargs):
        super(UnfeasibleVolatileResourcesProblem, self).__init__(*args, **kwargs)
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


class InvalidableAPSelectionStruct(object):

    def __init__(self):
        """
        Structure to store the AP selection mapping as a shared object between all SFC constraint violation checkers.
        No variables should be accessed when the struct is invalid!
        """
        self.struct_valid = False
        self.current_setting_sfc_delay = float('inf')
        self.ap_selection = {}

    def __getitem__(self, subinterval_index):
        assert self.struct_valid
        return self.ap_selection[subinterval_index]

    def items(self):
        assert self.struct_valid
        for k, v in self.ap_selection.items():
            yield k, v

    def add_ap_selection_dict(self, full_selection : dict, current_setting_sfc_delay):
        self.struct_valid = True
        if current_setting_sfc_delay < self.current_setting_sfc_delay:
            self.current_setting_sfc_delay = current_setting_sfc_delay
            self.ap_selection = dict(full_selection)
        # otherwise we keep the current AP selection because it was set by a stricter SFC

    def invalidate(self):
        self.struct_valid = False
        self.current_setting_sfc_delay = float('inf')

    @property
    def is_valid(self):
        return self.struct_valid

