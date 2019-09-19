#!/usr/bin/python3

import networkx as nx
from amplpy import AMPL, DataFrame
import argparse

import graphs.generate_service as gs

AMPLInfraTypes = ['APs', 'servers', 'mobiles']

# TODO: refactor the loading to a class to avoid parameter multiplication and/or global variables
infra_type_sets = {itype: [] for itype in AMPLInfraTypes}

def fill_service(ampl: AMPL, service: gs.ServiceGMLGraph) -> None:
    # TODO: add edges
    vnfs, demands = [], []
    service_graph = ampl.param['serviceGraph'].value()

    for vnf_id, vnf_data in service.nodes(data=True):
        vnfs += [vnf_id]
        demands += [vnf_data[service.nf_demand_str]]

    # Set the VNFs
    ampl.set['vertices'][service_graph] = vnfs

    # Set their demands
    df = DataFrame('vertices', 'demands')
    df.setValues({
        vnf: demand
        for vnf, demand in zip(vnfs, demands)
    })
    ampl.setData(df)


def fill_infra(ampl: AMPL, infra: gs.InfrastructureGMLGraph) -> None:
    





    # vvvvvvvv WHAT WAS BEFORE vvvvvvvvv



    # TODO: add edges
    infra_graph = ampl.param['infraGraph'].value()
    infra_set = []
    resources = {}
    cost_unit_demand = {}
    for ampl_infra_type, id_list in zip(AMPLInfraTypes,
                                        [infra.access_point_ids, infra.server_ids, infra.mobile_ids]):
        for infra_id in id_list:
            infra_data = infra.node[infra_id]
            infra_name = infra_data['name']
            # NOTE: maybe we should use ID-s instead of names (ID uniqueness is ensured by the networkx structure, name not surely unique)
            infra_set.append(infra_name)
            infra_type_sets[ampl_infra_type].append(infra_name)
            resources[infra_name] = infra_data[infra.infra_node_capacity_str]
            cost_unit_demand[infra_name] = infra_data[infra.infra_unit_cost_str]

    # Set AMPL object
    for ampl_infra_type in AMPLInfraTypes:
        ampl.set[ampl_infra_type] = infra_type_sets[ampl_infra_type]

    ampl.set['vertices'][infra_graph] = infra_set
    df = DataFrame('vertices', 'resources')
    df.setValues(resources)
    ampl.setData(df)

    df = DataFrame('vertices', 'cost_unit_demand')
    df.setValues(cost_unit_demand)
    ampl.setData(df)


def fill_AP_coverage_probabilities(ampl: AMPL, interval_length: int) -> None:
    subintervals = [i for i in range(1, interval_length + 1)]
    APs = infra_type_sets[AMPLInfraTypes['APs']]
    df = DataFrame(('AP_name', 'subinterval'), 'prob')
    df.setValues({(AP, subint): 0.9 for AP in APs for subint in subintervals})
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
    ampl.set['graph'] = infra.endpoint_ids + infra.access_point_ids +\
            infra.server_ids + infra.mobile_ids + service.vnfs

    ampl.param['infraGraph'] = infra.endpoint_ids + infra.access_point_ids +\
            infra.server_ids + infra.mobile_ids
    ampl.param['serviceGraph'] = service.vnfs
    # TODO @Jorge: continue from here on
    fill_service(ampl, service)
    fill_infra(ampl, infra)
    # TODO: read infraGraph interval_length serviceGraph etc. from the service and infra
    return ampl


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Given network service and' + \
                                                 ' infrastructure graphs, it creates an AMPL .dat file')

    parser.add_argument('model', metavar='model', type=str,
                        help='Path to the AMPL model')
    parser.add_argument('service', metavar='service', type=str,
                        help='Path to the network service GML file')
    parser.add_argument('infra', metavar='infra', type=str,
                        help='Path to the infrastructure GML file')
    parser.add_argument('out', metavar='out', type=str,
                        help='Path to the output where .dat is created')
    parser.add_argument('interval_length', metavar='time_len', type=int,
                        help='Time interval length')

    args = parser.parse_args()

    # Read .gml files of the network service and infrastructure graphs
    infra = nx.read_gml(path=args.infra, label='id')
    service = nx.read_gml(path=args.service, label='id')

    # Fill our model data
    ampl = AMPL()
    ampl.read(args.model)
    ampl.set['graph'] = [args.infra, args.service]
    ampl.param['infraGraph'] = args.infra
    ampl.param['serviceGraph'] = args.service
    ampl.param['interval_length'] = args.interval_length
    ampl.param['coverage_threshold'] = 0.95

    fill_service(ampl, service)
    fill_infra(ampl, infra)
    fill_AP_coverage_probabilities(ampl, args.interval_length)
    ampl.exportData(datfile=args.out)

