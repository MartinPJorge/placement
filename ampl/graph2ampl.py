#!/usr/bin/python3

import networkx as nx
from amplpy import AMPL, DataFrame
import argparse

import graphs.generate_service as gs

AMPLInfraTypes = ['APs', 'servers', 'mobiles']

# TODO: refactor the loading to a class to avoid parameter multiplication and/or global variables
infra_type_sets = {itype: [] for itype in AMPLInfraTypes}

def fill_service(ampl: AMPL, service: gs.ServiceGMLGraph) -> None:
    ampl.param['vertices']['service'] = service.vnfs
    ampl.set['edges']['service'] = [(c1,c2) in service.edges()]

    # set the CPU demands
    ampl.getParameter('demands').setValues({
        vnf: props['cpu']
        for vnf,props in service.nodes(data=True)
    })


def fill_infra(ampl: AMPL, infra: gs.InfrastructureGMLGraph) -> None:
    # All the infra graph vertices
    ampl.set['vertices']['infra'] = infra.endpoint_ids +\
            infra.access_point_ids + infra.server_ids + infra.mobile_ids
    ampl.set['APs'] = infra.access_point_ids
    ampl.set['servers'] = infra.server_ids
    ampl.set['mobiles'] = infra.mobile_ids

    # Infrastructure edges
    ampl.set['edges']['infra'] = [(c1,c2) in infra.edges()]
    
    # set the CPU capabilities
    ampl.getParameter('resources').setValues({
        node: props['cpu']
        for node,props in infra.nodes(data=True)
    })

    # TODO: put the cost unit demand
    ampl.getParameter('cost_unit_demand').setValues({
        node: props['unit_cost']
        for node,props in infra.nodes(data=True)
    })

    # TODO: fill the battery probability constraints


def fill_AP_coverage_probabilities(ampl: AMPL, interval_length: int) -> None:
    subintervals = [i for i in range(1, interval_length + 1)]
    APs = infra_type_sets[AMPLInfraTypes['APs']]
    df = DataFrame(('AP_name', 'subinterval'), 'prob')
    df.setValues({(AP, subint): 0.9 for AP in APs for subint in subintervals})
    ampl.param['prob_AP'].setValues(df)
    # TODO: refine this method to actually fill with the coverage prob


def get_complete_ampl_model_data(ampl_model_path, service : gs.ServiceGMLGraph, infra : gs.InfrastructureGMLGraph) -> AMPL:
    """
    Reads all service and infrastructure information to AMPL python data structure

    :param service:
    :param infra:
    :return:
    """
    ampl = AMPL()
    ampl.read(ampl_model_path)
    ampl.set['graph'] = ['infra', 'service']
    ampl.param['infraGraph'] = 'infra'
    ampl.param['serviceGraph'] = 'service'

    # TODO: interval_length 
    interval_length = 10

    fill_AP_coverage_probabilities(ampl, interval_length)

    # TODO @Jorge: continue from here on
        # fill the affinity variable

    fill_service(ampl, service)
    fill_infra(ampl, infra)
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

