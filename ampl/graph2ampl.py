#!/usr/bin/python3
import sys
from amplpy import AMPL, DataFrame
import logging
from rainbow_logging_handler import RainbowLoggingHandler

import graphs.generate_service as gs


class AMPLDataConstructor(object):

    def __init__(self, log=None):
        if log is None:
            self.log = logging.Logger(self.__class__.__name__)
        else:
            self.log = log.getChild(self.__class__.__name__)
        handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
        formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG)

    def fill_service(self, ampl: AMPL, service: gs.ServiceGMLGraph) -> None:
        ampl.set['vertices'][service.name] = service.vnfs
        ampl.set['edges'][service.name] = [
            (service.nodes[c1][service.node_name_str],
                service.nodes[c2][service.node_name_str]) for c1,c2 in service.edges()]

        # Parse SFC-s from the service graph
        sfc_id = 1
        sfc_path_dict = {}
        sfc_delay_dict = {}
        for sfc_delay, sfc_edge_id_path in service.sfc_delays_list:
            # the generator's edges contain node ID-s, we need node names.
            sfc_edge_name_path = map(lambda t: (service.nodes[t[0]][service.node_name_str],
                                                service.nodes[t[1]][service.node_name_str]), sfc_edge_id_path)
            sfc_name = 'sfc'+str(sfc_id)
            sfc_path_dict[sfc_name] = list(sfc_edge_name_path)
            sfc_delay_dict[sfc_name] = sfc_delay
            self.log.debug("Adding SFC {} on path {}".format(sfc_name, sfc_path_dict[sfc_name]))
            sfc_id += 1
        ampl.set['SFCs'] = list(sfc_path_dict.keys())
        for sfc_name in sfc_path_dict.keys():
            ampl.set['SFC_paths'][sfc_name] = sfc_path_dict[sfc_name]
        ampl.getParameter('SFC_max_delays').setValues(sfc_delay_dict)

        # set the VNF demands
        ampl.getParameter('demands').setValues({
            props[service.node_name_str]: props[service.nf_demand_str]
            for vnf, props in service.nodes(data=True)
        })

    def fill_infra(self, ampl: AMPL, infra: gs.InfrastructureGMLGraph) -> None:
        # Get the infrastructure nodes' names
        self.endpoint_names = [infra.nodes[id_][infra.node_name_str]
            for id_ in infra.endpoint_ids]
        self.access_point_names = [infra.nodes[id_][infra.node_name_str]
            for id_ in infra.access_point_ids]
        self.server_names = [infra.nodes[id_][infra.node_name_str]
            for id_ in infra.server_ids]
        self.mobile_names = [infra.nodes[id_][infra.node_name_str]
            for id_ in infra.mobile_ids]
        self.infra_names = self.endpoint_names + self.access_point_names + self.server_names + \
                           self.mobile_names

        # All the infra graph vertices
        ampl.set['vertices'][infra.name] = self.infra_names
        ampl.set['APs'] = self.access_point_names
        ampl.set['servers'] = self.server_names
        ampl.set['mobiles'] = self.mobile_names

        # add the mobile cluster's master node
        self.master_mobile_id = list(infra.ap_coverage_probabilities.keys())[0]
        self.master_mobile_name  = infra.nodes[self.master_mobile_id][infra.node_name_str]
        ampl.param['master'] = self.master_mobile_name
        self.log.debug("Setting master mobile {}".format(self.master_mobile_name))

        # Infrastructure edges
        ampl.set['edges'][infra.name] = [(infra.nodes[c1][infra.node_name_str],
            infra.nodes[c2][infra.node_name_str]) for c1,c2 in infra.edges()]

        # set the node resource capabilities
        ampl.getParameter('resources').setValues({
            props[infra.node_name_str]: props[infra.infra_node_capacity_str]
            for node, props in infra.nodes(data=True) if node not in infra.ignored_nodes_for_optimization
        })

        ampl.getParameter('cost_unit_demand').setValues({
            props[infra.node_name_str]: props[infra.infra_unit_cost_str]
            for node,props in infra.nodes(data=True) if node not in infra.ignored_nodes_for_optimization
        })

        # fill the battery probability constraints
        ampl.getParameter('max_used_battery').setValues({
            mobile_node: infra.full_loaded_battery_alive_prob
            for mobile_node in self.mobile_names
        })
        ampl.getParameter('min_used_battery').setValues({
            mobile_node: infra.unloaded_battery_alive_prob
            for mobile_node in self.mobile_names
        })

    def fill_AP_coverage_probabilities(self, ampl: AMPL, infra: gs.InfrastructureGMLGraph, interval_length: int) -> None:
        subintervals = [i for i in range(1, interval_length + 1)]
        df = DataFrame(('AP_name', 'subinterval'), 'prob')
        single_cluster = infra.ap_coverage_probabilities[self.master_mobile_id]
        df.setValues({(infra.nodes[ap_id][infra.node_name_str], subint): single_cluster[subint][ap_id]
                      for subint in subintervals for ap_id in infra.access_point_ids})
        # df.setValues({(AP, subint): infra. for ap_id in infra.access_point_ids for subint in subintervals})
        ampl.param['prob_AP'].setValues(df)


def get_complete_ampl_model_data(ampl_model_path, service : gs.ServiceGMLGraph, infra : gs.InfrastructureGMLGraph, log=None) -> AMPL:
    """
    Reads all service and infrastructure information to AMPL python data structure

    :param service:
    :param infra:
    :return:
    """
    ampl = AMPL()
    ampl.read(ampl_model_path)
    ampl.set['graph'] = [infra.name, service.name]
    ampl.param['infraGraph'] = infra.name
    ampl.param['serviceGraph'] = service.name

    # interval_length 
    ampl.param['interval_length'] = infra.time_interval_count

    constructor = AMPLDataConstructor(log)
    constructor.fill_service(ampl, service)
    constructor.fill_infra(ampl, infra)
    constructor.fill_AP_coverage_probabilities(ampl, infra, infra.time_interval_count)

    return ampl


