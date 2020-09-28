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
    root_logger.info("Generating service graph...")
    service_instance = gs.ServiceGMLGraph(substrate_network, **config['service'], log=root_logger)

    # Read the waypoints path
    paths_graph = nx.read_gml(
            config['infrastructure']['cluster_move_waypoints'],
            destringizer=float)
    waypoints = nx.shortest_path(paths_graph,
            source=config['infrastructure']['cluster_src_dst_tuples'][0][0],
            target=config['infrastructure']['cluster_src_dst_tuples'][0][1],
            weight='distance')
    print('These are the waypoints: ', path)




    for t in range(config['time_interval_count']):
        # derive the robot position
        lat, lon = position(time=t, path=waypoints,
                            duration=config['time_interval_count']-1)

    # ================
    # == pseudocode ==
    # ================
    #
    ## select master robot
    ## for t in [1..24]:
    ##     obtain robot position
    ##     update robot position
    ##     connect master robot to a cell_t
    ##     mapping[AP_selection][t] = cell_t
    ##     if t=1:
    ##         run FMC.map()
    ##     elif t >= 2:
    ##         run FMC.migrate()



    for n in service_instance.nodes(data=True):
        print(n)
    for n in substrate_network.nodes(data=True):
        print(n)

    print(list(substrate_network.nodes))

