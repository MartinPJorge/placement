#!/usr/bin/python3
import sys
from amplpy import AMPL, DataFrame
import logging
from rainbow_logging_handler import RainbowLoggingHandler

import graphs.generate_service as gs


class AMPLDataConstructor(object):

    def __init__(self, optimization_kwargs, log=None):
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
        self.optimization_kwargs = optimization_kwargs

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

        # NOTE: infrastructure edges are never used anywhere in the formulation!
        # Infrastructure edges
        # NOT ALL INFRA edges should be added!
        # ampl.set['edges'][infra.name] = [(infra.nodes[c1][infra.node_name_str],
        #     infra.nodes[c2][infra.node_name_str]) for c1,c2 in infra.edges()]

        # set the node resource capabilities
        ampl.getParameter('resources').setValues({
            props[infra.node_name_str]: props[infra.infra_node_capacity_str]
            for node, props in infra.nodes(data=True) if node not in infra.ignored_nodes_for_optimization
        })

        # all non-ignored nodes have a cost which is interpreted as a unit cost.
        # (it is set for AP-s too, but they can never host VNFs in the current model)
        ampl.getParameter('cost_unit_demand').setValues({
            props[infra.node_name_str]: props[infra.infra_unit_cost_str]
            for node,props in infra.nodes(data=True) if node not in infra.ignored_nodes_for_optimization
        })

        # set usage cost of AP
        ampl.getParameter('cost_using_AP').setValues({
            props[infra.node_name_str]: props[infra.access_point_usage_cost_str]
            for node, props in infra.nodes(data=True) if node in infra.access_point_ids
        })

        # fill the battery probability constraints
        ampl.getParameter('full_loaded_battery_alive_prob').setValues({
            mobile_node: infra.full_loaded_battery_alive_prob
            for mobile_node in self.mobile_names
        })
        ampl.getParameter('unloaded_battery_alive_prob').setValues({
            mobile_node: infra.unloaded_battery_alive_prob
            for mobile_node in self.mobile_names
        })

    def fill_AP_coverage_probabilities(self, ampl: AMPL, infra: gs.InfrastructureGMLGraph, interval_length: int) -> None:
        subintervals = [i for i in range(1, interval_length + 1)]
        df = DataFrame(('AP_name', 'subinterval'), 'prob')
        single_cluster = infra.ap_coverage_probabilities[self.master_mobile_id]
        df.setValues({(infra.nodes[ap_id][infra.node_name_str], subint): single_cluster[subint][ap_id]
                      for subint in subintervals for ap_id in infra.access_point_ids})
        ampl.param['prob_AP'].setValues(df)

    def fill_global_optimization_params(self, ampl : AMPL):
        # minimal probability of covering the mobile cluster by the selected access point at all times
        ampl.getParameter('coverage_threshold').set(float(self.optimization_kwargs['coverage_threshold']))
        # Least probability which the mobile clusters are not depleted by the end of the
        # optimization interval with the allocated load.
        ampl.getParameter('battery_threshold').set(float(self.optimization_kwargs['battery_threshold']))
        # must be the same as it is set for the infrastructure for the optimization task generation
        ampl.getParameter('interval_length').set(float(self.optimization_kwargs['time_interval_count']))

    def fill_placement_policies(self, ampl : AMPL, service : gs.ServiceGMLGraph, infra : gs.InfrastructureGMLGraph):
        policy_dict = {}
        self.log.info("Reading placement policies from service...")
        self.log.debug(" "*5 + " ".join(d[infra.node_name_str] for i, d in infra.nodes(data=True) if i not in infra.ignored_nodes_for_optimization))
        for vnf_id, vnf_data in service.nodes(data=True):
            string_of_a_row = ""
            for infra_node_id, infra_node_data in infra.nodes(data=True):
                if infra_node_id not in infra.ignored_nodes_for_optimization:
                    ampl_df_key = (vnf_data[service.node_name_str], infra_node_data[infra.node_name_str])
                    if service.location_constr_str in vnf_data:
                        if infra_node_id in vnf_data[service.location_constr_str]:
                            policy_dict[ampl_df_key] = 1
                        else:
                            policy_dict[ampl_df_key] = 0
                    else:
                        policy_dict[ampl_df_key] = 1
                    string_of_a_row += " "*len(infra_node_data[infra.node_name_str]) + str(policy_dict[ampl_df_key])
            self.log.debug("{}:".format(vnf_data[service.node_name_str]) + string_of_a_row)
        df = DataFrame(('vnf_name', 'infra_node_name'), 'is_allowed')
        df.setValues(policy_dict)
        ampl.param['policy'].setValues(df)

    def fill_delay_values(self, ampl : AMPL, infra : gs.InfrastructureGMLGraph):
        self.log.info("Setting time-invariant delay matrices from the infrastructure distance calculation info.")
        # set delay of AP
        ampl.getParameter('AP_mobile_delay').setValues({
            props[infra.node_name_str]: props[infra.access_point_delay_str]
            for node, props in infra.nodes(data=True) if node in infra.access_point_ids
        })

        # set delays between APs and servers
        ap_server_delay_dict = {}
        for ap_id in infra.access_point_ids:
            for infra_id in infra.server_ids:
                ampl_df_key = (infra.nodes[ap_id][infra.node_name_str], infra.nodes[infra_id][infra.node_name_str])
                # delay between the APs and servers is time-invariant
                ap_server_delay_dict[ampl_df_key] = infra.delay_distance(ap_id, infra_id, 1)
        df = DataFrame(("AP_name", "infra_node_name"), "delay")
        df.setValues(ap_server_delay_dict)
        ampl.param['AP_server_delay'].setValues(df)

        # set delays between servers
        server_server_delay_dict = {}
        for infra_id1 in infra.server_ids:
            for infra_id2 in infra.server_ids:
                ampl_df_key = (infra.nodes[infra_id1][infra.node_name_str], infra.nodes[infra_id2][infra.node_name_str])
                # delay between servers are time invariant
                server_server_delay_dict[ampl_df_key] = infra.delay_distance(infra_id1, infra_id2, 1)
        df = DataFrame(("infra_node_name1", "infra_node_name2"), "delay")
        df.setValues(server_server_delay_dict)
        ampl.param['server_server_delay'].setValues(df)

        # set mobile internal delays
        mobile_mobile_delay_dict = {}
        for mobile_id1 in infra.mobile_ids:
            for mobile_id2 in infra.mobile_ids:
                ampl_df_key = (infra.nodes[mobile_id1][infra.node_name_str], infra.nodes[mobile_id2][infra.node_name_str])
                mobile_mobile_delay_dict[ampl_df_key] = infra.delay_distance(mobile_id1, mobile_id2, 1)
        df = DataFrame(("mobile_name1", "mobile_name2"), "delay")
        df.setValues(mobile_mobile_delay_dict)
        ampl.param['mobile_mobile_delay'].setValues(df)


def get_complete_ampl_model_data(ampl_model_path, service : gs.ServiceGMLGraph, infra : gs.InfrastructureGMLGraph,
                                 optimization_kwargs : dict, log=None) -> AMPL:
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

    constructor = AMPLDataConstructor(optimization_kwargs, log)
    constructor.fill_global_optimization_params(ampl)
    constructor.fill_service(ampl, service)
    constructor.fill_infra(ampl, infra)
    constructor.fill_AP_coverage_probabilities(ampl, infra, infra.time_interval_count)
    constructor.fill_placement_policies(ampl, service, infra)
    constructor.fill_delay_values(ampl, infra)

    return ampl


