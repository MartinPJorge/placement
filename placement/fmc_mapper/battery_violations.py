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

###########
###########
###########
###########    ### REMOVE FROM HERE
###########
###########    # Print service and nodes info
###########    ### for n in ns.nodes(data=True):
###########    ###     print(n)
###########    ### for n in ns.edges(data=True):
###########    ###     print(n)
###########    ### for n in infra.nodes(data=True):
###########    ###     print(n)
###########
###########
###########    # Read the waypoints path
###########    paths_graph = nx.read_gml(
###########            config['infrastructure']['cluster_move_waypoints'],
###########            destringizer=float)
###########    waypoints = nx.shortest_path(paths_graph,
###########            source=config['infrastructure']['cluster_src_dst_tuples'][0][0],
###########            target=config['infrastructure']['cluster_src_dst_tuples'][0][1],
###########            weight='distance')
###########    print('These are the waypoints: ', waypoints)
###########
###########
###########    # Obtain master robot and cell nodes
###########    master = list(substrate_network.ap_coverage_probabilities.keys())[0]
###########    cell_nodes = filter(lambda n: substrate_network.nodes[n]['type'] == 'cell',
###########                    substrate_network.nodes)
###########
###########
###########    # Instantiate the FMC mapper
###########    fog_checker = CheckBasicGraphs()
###########    fmc_mapper = FMCMapper(checker=fog_checker)
###########
###########
###########    attached_cells = [] # list of cells connected to the robot
###########    all_worked = True
###########    mapping = {}
###########    result = {'AP_selection': {}} # for the resulting JSON dumped
###########    print('NS edges')
###########    for edge in ns.edges():
###########        print(f'  {edge}')
###########    for t in range(1,config['infrastructure']['time_interval_count']+1):
###########        mapping[t] = {}
###########        start = time.time()
###########        print(f't={t}')
###########        # dettach the robot from previous cells
###########        while len(attached_cells) > 0:
###########            infra.remove_edge(master, attached_cells.pop())
###########
###########        # select the AP with maximum coverage probability
###########        # substrate_network.ap_coverage_probabilities = {
###########        #   master_id: {
###########        #      time: {
###########        #           cell_id: coverage probability
###########        #            ...
###########        #      }
###########        #       ...
###########        #   }
###########        # }
###########        coverage_t = substrate_network.ap_coverage_probabilities[master][t]
###########        best_cell = reduce(lambda c1,c2: c1 if coverage_t[c1] > coverage_t[c2]\
###########                                            else c2, coverage_t.keys())
###########        result['AP_selection'][t] = best_cell
###########        infra.add_edge(master, best_cell, bandwidth=100,
###########            delay=substrate_network.nodes[best_cell]['delay'])
###########        attached_cells += [best_cell]
###########
###########        print(f'  best_cell={best_cell}')
###########
###########
###########        if t == 1:
###########            worked_cs = True # Map all connected components in NS
###########            for c in nx.connected_components(ns):
###########                print(f'mapping connected_component {c}')
###########                nsc = ns.subgraph(c)#.copy()
###########                mappingc = fmc_mapper.map(infra=infra, ns=nsc, adj=200, tr=1,
###########                        ts=config['infrastructure']['time_interval_count'])
###########                worked_cs = worked_cs and mappingc['worked']
###########                for k in mappingc:
###########                    mapping[t][k] = mappingc[k]
###########
###########            mapping[t]['worked'] = worked_cs
###########            mapping[0] = dict(mapping[t])
###########
###########            print(f'mapping[{t}]={mapping[t]}')
###########
###########        # Perform migration (even at t=0, so it meets delay restrictions)
###########        worked_cs = True
###########        mapping[t] = dict(mapping[t-1])
###########        for c in nx.connected_components(ns):
###########            print(f'migrating connected_component {c}')
###########            nsc = ns.subgraph(c)#.copy()
###########            mappingc = fmc_mapper.handover(infra=infra, ns=nsc,
###########                    prev_mapping=mapping[t-1],
###########                    tr=1, ts=config['infrastructure']['time_interval_count'],
###########                    Sl=sum(map(lambda dp: dp[0],
###########                        service_instance.sfc_delays_list)),
###########                    paths=10)
###########            # No cell used, keep previous mapping
###########            if mappingc == None:
###########                worked_cs = False
###########                continue
###########            else:
###########                worked_cs = worked_cs and mappingc['worked']
###########            # add mappings of the connected component
###########            for k in mappingc:
###########                mapping[t][k] = mappingc[k]
###########        if worked_cs != None:
###########            mapping[t]['worked'] = worked_cs
###########
###########        print('worked_cs',worked_cs)
###########        # Keep track if all mappings have worked
###########        all_worked = all_worked and mapping[t]['worked']
###########
###########        result[t] = {
###########            ns.nodes[n]['name']: infra.nodes[mapping[t][n]]['name']
###########            for n in ns.nodes
###########        }
###########        result[t]['worked'] = mapping[t]['worked']
###########        result[t]['Objective_value'] = fmc_mapper.mapping_cost(
###########                infra=infra, ns=ns, mapping=mapping[t], with_cell=False)
###########        end = time.time()
###########        result[t]['Running_time'] = end - start
###########
###########
###########        print(f'migration mapping[{t}]={mapping[t]}')
###########
###########
###########    # DUmp results as JSON
###########    result['worked'] = all_worked
###########    ts = list(result['AP_selection'].keys())
###########    result['Running_time'] = sum(map(lambda t: result[t]['Running_time'], ts))
###########    result['Objective_value'] = sum(map(lambda t:
###########                result[t]['Objective_value'] / len(ts), ts)) +\
###########        sum(map(lambda t: infra.nodes[result['AP_selection'][t]]['cost'], ts))
###########    with open(out, 'w') as f:
###########        json.dump(result, f, indent=4)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Checks if the FMC solutions meet battery reqs.")
    parser.add_argument('battery_th', type=float, help='battery_threshold')
    args = parser.parse_args()

    count = 1
    for subdir, dirs, files in os.walk("../constructive_mapper/simulator/results/mobile_nf_loads_small_sweep"):
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

