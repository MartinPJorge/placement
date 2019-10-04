#!/usr/bin/python3

import networkx as nx
from amplpy import AMPL, DataFrame
import argparse

import graphs.generate_service as gs


class AMPLDataConstructor(object):

    def __init__(self):
        self.AMPLInfraTypes = ['APs', 'servers', 'mobiles']
        self.infra_type_sets = {itype: [] for itype in self.AMPLInfraTypes}

    def fill_service(self, ampl: AMPL, service: gs.ServiceGMLGraph) -> None:
        ampl.set['vertices'][service.name] = service.vnfs
        ampl.set['edges'][service.name] = [
            (service.nodes[c1][service.node_name_str],
                service.nodes[c2][service.node_name_str]) for c1,c2 in service.edges()]

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
        single_cluster = list(infra.ap_coverage_probabilities.values())[0]
        df.setValues({(infra.node[ap_id][infra.node_name_str], subint): single_cluster[subint][ap_id]
                      for subint in subintervals for ap_id in infra.access_point_ids})
        # df.setValues({(AP, subint): infra. for ap_id in infra.access_point_ids for subint in subintervals})
        ampl.param['prob_AP'].setValues(df)


def get_complete_ampl_model_data(ampl_model_path, service : gs.ServiceGMLGraph, infra : gs.InfrastructureGMLGraph) -> AMPL:
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

    constructor = AMPLDataConstructor()
    constructor.fill_service(ampl, service)
    constructor.fill_infra(ampl, infra)
    constructor.fill_AP_coverage_probabilities(ampl, infra, infra.time_interval_count)

    return ampl


