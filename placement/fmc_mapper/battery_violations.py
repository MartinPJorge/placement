import time
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


violations_dict = {}
# {
#   "#vnfs": {
#     'success': 2,
#     'fail': 4
#   },
#   ...
#}

def check_battery(config, mapping, battery_th):
    """Checks if enough battery in the battery threshold experiments.
    Checks for the FMC solutions.

    :config: configuration YAML dictionary (already parsed)
    :mapping: a NS->infra mapping over time

    :Note: the paths in the config file must be parsed so
           they can open directly inside this function
    """

    # Generate both the infrastructure and service graph
    root_logger = logging.Logger('FMC volatile sims logger')
    root_logger.info("Generating infrastructure...")
    substrate_network = gs.InfrastructureGMLGraph(**config['infrastructure'], log=root_logger)

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


    # Build name -> id mappings
    service_instance_id_of = {
        service_instance.nodes[id_]['name']: id_
        for id_ in service_instance.nodes
    }
    substrate_network_id_of = {
        substrate_network.nodes[id_]['name']: id_
        for id_ in substrate_network.nodes
    }


    avg_loads = {
        infra_id: 0
        for infra_id in filter(lambda n:
            'fog' in substrate_network.nodes[n]['name'],
        substrate_network.nodes)
    }


    # Derive the average load for every robot over time [0, 1, ..., T]
    T = len(list(filter(lambda k: len(k) < 3, mapping.keys())))
    for t in filter(lambda k: len(k) < 3, mapping.keys()):
        for vname in filter(lambda k: "nf" in k, mapping[t].keys()):
            vnf_id = service_instance_id_of[vname]
            robot_id = substrate_network_id_of[mapping[t][vname]]
            if robot_id in avg_loads:
                avg_loads[robot_id] += 1/T * service_instance.nodes[vnf_id]['cpu']

    # Check if any robot violated the battery restriction
    battery_deads = []
    for robot_id in avg_loads:
        linear_coeff = substrate_network.unloaded_battery_alive_prob - substrate_network.full_loaded_battery_alive_prob
        probability = substrate_network.unloaded_battery_alive_prob -\
            avg_loads[robot_id]/substrate_network.nodes[robot_id]['cpu'] * linear_coeff

        battery_deads += [probability < battery_th]

    battery_died = any(battery_deads)
    print(battery_died, 'battery_died')
    mobile_nfs_per_sfc = config['service']['mobile_nfs_per_sfc']
    if mobile_nfs_per_sfc not in violations_dict:
        violations_dict[mobile_nfs_per_sfc] = {
            'success': 0,
            'fail': 0
        }

    success = mapping['worked'] and (not battery_died)
    if success:
        violations_dict[mobile_nfs_per_sfc]['success'] += 1
    else:
        violations_dict[mobile_nfs_per_sfc]['fail'] += 1




if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Checks if the FMC solutions meet battery reqs.")
    parser.add_argument('experiments_dir', type=str,
            help='path to experiments\' directory')
    parser.add_argument('battery_th', type=float, help='battery_threshold')
    args = parser.parse_args()

    count = 1
    #nf_loads_dir = "../constructive_mapper/simulator/results/mobile_nf_loads_small_sweep"
    for subdir, dirs, files in os.walk(args.experiments_dir):
        for file in files:



            if file == 'config.yml':
                print(count, subdir, file)
                count+=1

                # Read the YAML configuration file
                config_path = os.path.join(subdir, file)
                config = None
                with open(config_path) as f:
                    config = yaml.load(f.read(), Loader=yaml.FullLoader)

                # Update GMLs paths
                way_path = config['infrastructure']['cluster_move_waypoints']
                config['infrastructure']['cluster_move_waypoints'] =\
                        '/'.join(['..','constructive_mapper'] +\
                                way_path.split('/')[1:])
                block_path = config['infrastructure']['coverage_blocking_areas']
                config['infrastructure']['coverage_blocking_areas'] =\
                        '/'.join(['..','constructive_mapper'] +\
                                block_path.split('/')[1:])
                infra_path = config['infrastructure']['gml_file']
                config['infrastructure']['gml_file'] =\
                        '/'.join(['..','constructive_mapper'] +\
                                infra_path.split('/')[1:])

                mapping = subdir + '/soa_solution.json'
                with open(mapping, 'r') as f:
                    mapping = json.load(f)

                # RUn and store result
                check_battery(config, mapping, args.battery_th)

    print(json.dumps(violations_dict))








    # for n in substrate_network.nodes(data=True):
    #     print(n)

    # print(list(substrate_network.nodes))

