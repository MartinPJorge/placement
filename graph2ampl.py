#!/usr/bin/python3

import networkx as nx
from amplpy import AMPL, DataFrame
import argparse

InfraTypes = {
    'APs': "AP",
    'servers': "server",
    'mobiles': "mobile"
}

infra_type_sets = {itype: [] for itype in InfraTypes.values()}

def fill_service(ampl: AMPL, service: nx.classes.graph.Graph) -> None:
    vnfs, demands = [], []
    service_graph = ampl.param['serviceGraph'].value()

    for vnf_id, vnf_data in service.nodes(data=True):
        vnfs += [vnf_data['name']]
        demands += [vnf_data['demand']]

    # Set the VNFs
    ampl.set['vertices'][service_graph] = vnfs

    # Set their demands
    df = DataFrame('vertices', 'demands')
    df.setValues({
        vnf: demand
        for vnf, demand in zip(vnfs, demands)
    })
    ampl.setData(df)


def fill_infra(ampl: AMPL, infra: nx.classes.graph.Graph) -> None:
    infra_graph = ampl.param['infraGraph'].value()
    infra_set = []
    resources = {}
    cost_unit_demand = {}
    for infra_id, infra_data in infra.nodes(data=True):
        infra_name = infra_data['name']
        infra_set.append(infra_name)
        infra_type_sets[infra_data['type']].append(infra_name)
        resources[infra_name] = infra_data['resource']
        cost_unit_demand[infra_name] = infra_data['cost']

    # Set AMPL object
    for itype, infra_set_name in InfraTypes.items():
        ampl.set[itype] = infra_type_sets[infra_set_name]

    ampl.set['vertices'][infra_graph] = infra_set
    df = DataFrame('vertices', 'resources')
    df.setValues(resources)
    ampl.setData(df)

    df = DataFrame('vertices', 'cost_unit_demand')
    df.setValues(cost_unit_demand)
    ampl.setData(df)


def fill_AP_coverage_probabilities(ampl: AMPL, interval_length: int) -> None:
    subintervals = [i for i in range(1, interval_length + 1)]
    APs = infra_type_sets[InfraTypes['APs']]
    df = DataFrame(('AP_name', 'subinterval'), 'prob')
    df.setValues({(AP, subint): 0.9 for AP in APs for subint in subintervals})
    ampl.param['prob_AP'].setValues(df)


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

