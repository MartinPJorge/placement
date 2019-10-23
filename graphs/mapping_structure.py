from .generate_service import InfrastructureGMLGraph, ServiceGMLGraph


class VolatileResourcesMapping(dict):

    # key to store a bool for indicating whether it is a successful mapping (taken from the AbstractMapper's earlier realizations)
    WORKED = 'worked'
    # key to store a dict of AP names, for each time instance which is selected to serve the mobility cluster.
    AP_SELECTION = 'AP_selection'

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
            # keyed by subinterval index and value is AP id
            self[VolatileResourcesMapping.AP_SELECTION] = {}

    def add_access_point_selection(self, subinterval : int, ap_name):
        self[VolatileResourcesMapping.AP_SELECTION][int(subinterval)] = ap_name

    def get_access_point_selection(self, subinterval : int):
        return self[VolatileResourcesMapping.AP_SELECTION][int(subinterval)]

    def validate_mapping(self, ns: ServiceGMLGraph, infra: InfrastructureGMLGraph):
        """
        Checks whether the mapping task defined by the ns and infra is solved by this mapping object

        :param ns:
        :param infra:
        :return:
        """
        if self[VolatileResourcesMapping.WORKED]:
            # if not all service nodes are mapped
            if not all({d[ns.node_name_str] in self for n, d in ns.nodes(data=True)}):
                return False
            # TODO: check AP selection
            # location constraints
            for nf, data in ns.nodes(data=True):
                if ns.location_constr_str in data:
                    location_constr_name = map(lambda x: infra.nodes[x][infra.node_name_str], data[ns.location_constr_str])
                    if self[data[ns.node_name_str]] not in location_constr_name:
                        return False

            # TODO: check other constraints
            # if we didnt return yet, all constraints are correct
            return True
        else:
            # if mapping is not 'worked' then it is valid.
            return True
