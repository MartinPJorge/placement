import json
import random
import networkx as nx
import scipy
import sys
import argparse
import yaml
import os
import logging
from rainbow_logging_handler import RainbowLoggingHandler
sys.path.append(os.path.abspath(".."))
import constructive_mapper.graphs.generate_service as gs
from mapper import FMCMapper
from checker import CheckBasicGraphs
from functools import reduce





def position(time: int, path: list, duration: int) -> tuple:
    # given a time instant, it determines the location under constant speed
    # the path is traveled in duration time slots
    # path is a list of (lat,lon) tuples
    # returns a (lat, lon) tuple

    total_distance = 0
    segments = {}
    for src, dst in zip(path[:-1], path[1:]):
        total_distance += haversine(src, dst, unit='m')
        segments[src,dst] = {'length': haversine(src, dst, unit='m')}


    # segments time correspondance
    t, traveled = 0, 0
    for (src,dst) in segments.keys:
        segments[src,dst]['start'] = t
        t += segments[src,dst]['length'] * duration / total_distance
        segments[src,dst]['end'] = t

    for (src,dst) in segments.keys:
        start, end = segments[src,dst]['start'], segments[src,dst]['end']
        if start <= time <= end:
            t_ = (time - start) / (end - start)
            return ((dst[0]-src[0])*t_ + src[0],
                    (dst[1]-src[1])*t_ + src[1])





if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Runs FMC mapper on @balazsbme algorithm")
    parser.add_argument('config', type=str, help='yaml config file')
    args = parser.parse_args()

    # Read the YAML configuration file
    config = None
    with open(args.config) as f:
        config = yaml.load(f.read(), Loader=yaml.FullLoader)


    # Generate both the infrastructure and service graph
    root_logger = logging.Logger('FMC volatile sims logger')
    root_logger.info("Generating infrastructure...")
    substrate_network = gs.InfrastructureGMLGraph(**config['infrastructure'], log=root_logger)
    infra = nx.Graph(substrate_network) # undirected version

    root_logger.info("Generating service graph...")
    service_instance = gs.ServiceGMLGraph(substrate_network, **config['service'], log=root_logger)
    nx.set_node_attributes(service_instance, {
        vnf: {'cpu': service_instance.nodes[vnf]['weight']}
        for vnf in service_instance.nodes
    })
    nx.set_edge_attributes(service_instance, {
        vl: {'bandwidth': 0}
        for vl in service_instance.edges
    })
    ns = nx.Graph(service_instance)




    for n in ns.nodes(data=True):
        print(n)
    for n in infra.nodes(data=True):
        print(n)
    for n in ns.edges(data=True):
        print(n)


    # Read the waypoints path
    paths_graph = nx.read_gml(
            config['infrastructure']['cluster_move_waypoints'],
            destringizer=float)
    waypoints = nx.shortest_path(paths_graph,
            source=config['infrastructure']['cluster_src_dst_tuples'][0][0],
            target=config['infrastructure']['cluster_src_dst_tuples'][0][1],
            weight='distance')
    print('These are the waypoints: ', waypoints)


    # Obtain master robot and cell nodes
    master = list(substrate_network.ap_coverage_probabilities.keys())[0]
    cell_nodes = filter(lambda n: substrate_network.nodes[n]['type'] == 'cell',
                    substrate_network.nodes)


    # Instantiate the FMC mapper
    fog_checker = CheckBasicGraphs()
    fmc_mapper = FMCMapper(checker=fog_checker)


    attached_cells = [] # list of cells connected to the robot
    mapping = {}
    for t in range(1,config['infrastructure']['time_interval_count']+1):
        # dettach the robot from previous cells
        while len(attached_cells) > 0:
            substrate_network.remove_edge(master, attached_cells.pop())

        # select the AP with maximum coverage probability
        # substrate_network.ap_coverage_probabilities = {
        #   master_id: {
        #      time: {
        #           cell_id: coverage probability
        #            ...
        #      }
        #       ...
        #   }
        # }
        coverage_t = substrate_network.ap_coverage_probabilities[master][t]
        best_cell = reduce(lambda c1,c2: c1 if coverage_t[c1] > coverage_t[c2]\
                                            else c2, coverage_t.keys())
        infra.add_edge(master, best_cell, bandwidth=100,
            delay=substrate_network.nodes[best_cell]['delay'])
        attached_cells += [best_cell]


        if t == 1:
            mapping[t] = fmc_mapper.map(infra=infra, ns=ns, adj=5, tr=1,
                    ts=config['infrastructure']['time_interval_count'])
            mapping[0] = dict(mapping[t])

        print(f'mapping[{t}]={mapping[t]}')

        # Perform migration (even at t=0, so it meets delay restrictions)
        mapping[t] = fmc_mapper.handover(infra=infra, ns=ns,
                prev_mapping=mapping[t-1],
                tr=1, ts=config['infrastructure']['time_interval_count'],
                Sl=sum(map(lambda dp: dp[0],
                    service_instance.sfc_delays_list)),
                cutoff=8)


        print(f'migration mapping[{t}]={mapping[t]}')






    # for n in substrate_network.nodes(data=True):
    #     print(n)

    # print(list(substrate_network.nodes))

