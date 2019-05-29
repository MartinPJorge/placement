from amplpy import AMPL, DataFrame, Environment
import argparse
import networkx as nx
import os
import sys
import json
import pandas as pd
import re
from utils import get_all_trails
from haversine import haversine



def check_endpoint_locs(infra: nx.classes.graph.Graph, config: dict) -> bool:
    """Checks if the locations of endpoints of the service, match with the
    ones present in the infrastructure graph

    :infra: nx.classes.graph.Graph: infrastructure graph
    :config: dict: configuration dictionary
    :returns: bool determining if they match

    """
    ends = [d for _,d in infra.nodes(data=True) if d['type'] == 'endpoint']
    for s in config['services']:
        service_g = nx.read_gml(s['graph'], label='id')
        for s_end in [d for _,d in service_g.nodes(data=True)\
                                if d['type'] == 'endpoint']:
            for end in ends:
                if s_end['name'] == end['name'] and\
                   (s_end['lon'] != end['lon'] or\
                    s_end['lat'] != end['lat']):
                    print('service', s['id'], 'contains endpoint',
                           s_end['name'], 'with location different than',
                           'infrastructure endpoint', end['name'])
                    return False

    return True


def fill_phy_nodes(ampl: AMPL, infra: nx.classes.graph.Graph,
                   config: dict) -> AMPL:
    """Fills the AMPL instance with the physical nodes, that is, with the
    endpoints and cNodes

    :ampl: AMPL: instance of the model with filled information 
    :infra: nx.classes.graph.Graph: infrastructure graph
    :config: dict: configuration dictionary
    :returns: None

    """
    
    cnodes, endpoints, reliab = [], [], []
    cnodes_cpu, cnodes_cpu_cost = [], []
    cnodes_radio, cnodes_radio_cost = [], []
    phynodes = []
    endpoint_locs = {}

    for node in infra.nodes():
        cnodes += [infra.nodes[node]['name']]
        cnodes_cpu += [infra.nodes[node]['cpu']]
        cnodes_cpu_cost += [infra.nodes[node]['resCost']]

        if infra.nodes[node]['type'] != 'endpoint':
            cnodes_radio += [infra.nodes[node]['radio']]
            cnodes_radio_cost += [infra.nodes[node]['radioCost']]
        else:
            endpoints += [infra.nodes[node]['name']]
            endpoint_locs[infra.nodes[node]['name']] = "(" +\
                str(infra.nodes[node]['lon']) + "," +\
                str(infra.nodes[node]['lat']) + ")"
        phynodes += [infra.nodes[node]['name']]
        reliab += [infra.nodes[node]['reliability']]
    time = list(range(config['endTime'] + 1))

    # Set the cNodes
    df = DataFrame('cNodes')
    df.setColumn('cNodes', cnodes)
    ampl.setData(df, 'cNodes')

    # Set the endpoints and their reliability
    end_reliab = {}
    for d in [d for _,d in infra.nodes(data=True) if d['type'] == 'endpoint']:
        crel = config['endReliabilities']
        end_reliab[d['name']] = 1 if d['name'] not in crel else crel[d['name']]
    df = DataFrame('endpoints')
    df.setColumn('endpoints', end_reliab.keys())
    df.addColumn('endReliability', end_reliab.values())
    ampl.setData(df, 'endpoints')
    print('end_reliabilities: ', end_reliab)

    # Set the endpoints' locations
    df = DataFrame('endpoints', 'locationE')
    df.setValues(endpoint_locs)
    ampl.setData(df)

    # Set the bfResources as just 'cpu' ==TODO latter considering all==
    ampl.set['bfResources'] = ['CPU']

    # Set capacity properties
    df = DataFrame(('cNodes', 'bfResources'), 'capacity')
    df.setValues({(cnode, 'CPU'): cnode_cpu
                for cnode, cnode_cpu in zip(cnodes, cnodes_cpu)})
    ampl.setData(df)
    
    # Set reliability properties
    df = DataFrame(('phyNodes', 't'), 'reliability')
    df.setValues({(phynode, t): reliability
                  for phynode, reliability in zip(phynodes, reliab)
                  for t in time})
    ampl.setData(df)

    # Set radio technologies
    ampl_radios = [] if ampl.getSet('radioTechs').size() == 0\
                     else ampl.getSet('radioTechs').getValues()
    radio_techs = set(nx.get_node_attributes(infra, 'radio').values())
    radio_techs = list(radio_techs.union(set(ampl_radios)))
    ampl.set['radioTechs'] = radio_techs

    # Set cnodes radio technologies
    df = DataFrame(('radioTechs', 'cNodes'), 'radiocNode')
    radio_atts = nx.get_node_attributes(infra, 'radio')
    df.setValues({
        (radio, n['name']): 1
        for radio in radio_techs
        for n_id,n in infra.nodes(data=True)
        if n_id in radio_atts and radio_atts[n_id] == radio
    })
    ampl.setData(df)

    # Set computational resources cost
    df = DataFrame(('cNodes', 'services', 'bfResources'), 'compResCost')
    df.setValues({
        (n['name'], s['id'], 'CPU'): n['resCost'] * s['compResCostFactor']
        for _,n in infra.nodes(data=True)
        for s in config['services']
    })
    ampl.setData(df)

    # Set radio resources cost
    df = DataFrame(('cNodes', 'services', 'bfResources'), 'radioResCost')
    df.setValues({
        (n['name'], s['id'], n['radio']):\
                n['radioCost'] * s['radioResCostFactor']
        for _,n in infra.nodes(data=True)
        for s in config['services']
    })
    ampl.setData(df)

    return ampl


def fill_links(ampl: AMPL, infra: nx.classes.graph.Graph,
               config: dict) -> AMPL:
    """Fills the physical links' data inside the model

    :ampl: AMPL: instance of the model with filled information 
    :infra: nx.classes.graph.Graph: infrastructure graph
    :config: dict: configuration dictionary
    :returns: None

    """

    time = list(range(config['endTime'] + 1))
    
    # Set the physical links 
    links = [(infra.nodes[n1]['name'], infra.nodes[n2]['name'])
             for n1,n2 in infra.edges()]
    links_reverse = list(map(lambda l: (l[1],l[0]), links))
    ampl.getSet('phyLinks').setValues(links + links_reverse)

    # Set the links' capacity
    bws = [d['bandwidth'] / 2 for n1,n2,d in infra.edges(data=True)]
    df = DataFrame(('phyNodeA', 'phyNodeB'), 'linkCap')
    df.setValues({
        (pl[0], pl[1]): bw
        for pl, bw in zip(links + links_reverse, bws + bws)
    })
    ampl.setData(df)

    # Set the links' delay (assume speed of light)
    delay = [] # in meters
    for n1,n2,d in infra.edges(data=True):
        if d['distanceUnits'] == 'meters':
            delay += [d['distance'] / 3e6]
        elif d['distanceUnits'] == 'kilometers':
            delay += [d['distance'] / 3e3]
        else:
            delay += [0]
    df = DataFrame(('phyNodeA', 'phyNodeB'), 'delay')
    df.setValues({
        (pl[0], pl[1]): d
        for pl, d in zip(links + links_reverse, delay + delay)
    })
    ampl.setData(df)

    # Set the links' reliability
    reliab = [d['reliability'] for _,_,d in infra.edges(data=True)]
    df = DataFrame(('phyNodeA', 'phyNodeB', 't'), 'linkReliability')
    df.setValues({
        (pl[0], pl[1], t): r
        for pl,r in zip(links + links_reverse, reliab + reliab)
        for t in time
    })
    ampl.setData(df)

    # Set the links' IDs
    link_ids = ['l' + str(id_) for id_ in range(len(links))]
    link_ids_reverse = ['l_r' + str(id_) for id_ in range(len(links_reverse))]
    ampl.getSet('linkIds').setValues(link_ids + link_ids_reverse)

    # Set up the phyLink indexed by ID by setting src and dst
    for l_id,l in zip(link_ids + link_ids_reverse, links + links_reverse):
        ampl.set['phyLinkSrc'][l_id] = [l[0]]
        ampl.set['phyLinkDst'][l_id] = [l[1]]

    # Specify the bandwidth cost
    cost = [d['trafficCost'] for _,_,d in infra.edges(data=True)]
    df = DataFrame(('phyNodeA', 'phyNodeB', 'services'), 'trafficCost')
    df.setValues({
        (pl[0], pl[1], s['id']): c * s['trafficCostFactor']
        for pl,c in zip(links + links_reverse, cost + cost)
        for s in config['services']
    })
    ampl.setData(df)

    return ampl

    
def fill_paths(ampl: AMPL, infra: nx.classes.graph.Graph,
               config: dict) -> None:
    """Fills the model with the path-related sets and parameters

    :ampl: AMPL: instance of the model with filled information 
    :infra: nx.classes.graph.Graph: infrastructure graph
    :config: dict: configuration dictionary
    :returns: None

    """
    links = [(infra.nodes[n1]['name'], infra.nodes[n2]['name'])
             for n1,n2 in infra.edges()]
    links_reverse = list(map(lambda l: (l[1],l[0]), links))
    link_ids = ['l' + str(id_) for id_ in range(len(links))]
    link_ids_reverse = ['l_r' + str(id_) for id_ in range(len(links_reverse))]
    link_2_id = {(l[0], l[1]): l_id
                for l,l_id in zip(links + links_reverse,
                                  link_ids + link_ids_reverse)}

    # Create the directed graph version
    dinfra = nx.DiGraph()
    for n1,n2,d in infra.edges(data=True):
        d_ = dict(d)
        d_['bandwidth'] = d['bandwidth'] / 2
        dinfra.add_edge(n1, n2, **d_)
        dinfra.add_edge(n2, n1, **d_)

        nx.set_node_attributes(dinfra, values={n1: infra.nodes[n1],
                                               n2: infra.nodes[n2]})

    # Prepare path belonging data frames
    cnode_in_path_df = DataFrame(('pathIdx', 'cNode'), 'cNodeInPath')
    link_in_path_df = DataFrame(('pathIdx', 'phyNodeA', 'phyNodeB'),
                                'phyLinkInPath')
    cnode_in_path = {}
    link_in_path = {}

    # Get all possible trail targets
    targets = []
    for target_type in config['trailTargets']:
        targets += [(t_id,t) for t_id,t in infra.nodes(data=True)\
                             if t['type'] == target_type]

    # Get all possible trails starting and finishing at targets
    path, curr_id, path_idxs = {}, 0, []
    for t_id, t_d in targets:
        trails = get_all_trails(G=dinfra, source=t_id,
                                target=[i for i,d in targets],
                                cutoff=2*config['cutoff'])
        for trail in map(nx.utils.pairwise, trails):
            path_idx = 'p' + str(curr_id)
            path_idxs += [path_idx]
            path[path_idx] = {'trail': list(trail),
                              'link_ids': []}
            print('path', path_idx, ':')
            for n1,n2 in path[path_idx]['trail']:
                n1_name = dinfra.nodes[n1]['name']
                n2_name = dinfra.nodes[n2]['name']
                print('\t', n1_name, n2_name)

                if dinfra.nodes[n1]['type'] != 'endpoint': # is cNode
                    cnode_in_path[(path_idx, n1_name)] = 1
                if dinfra.nodes[n2]['type'] != 'endpoint': # is cNode
                    cnode_in_path[(path_idx, n2_name)] = 1
                link_in_path[(path_idx, n1_name, n2_name)] = 1

                path['p' + str(curr_id)]['link_ids'] +=\
                        [link_2_id[n1_name,n2_name]]
            curr_id += 1


    # Set cNodeInPath phyLinkInPath
    cnode_in_path_df.setValues(cnode_in_path)
    link_in_path_df.setValues(link_in_path)
    ampl.setData(cnode_in_path_df)
    ampl.setData(link_in_path_df)

    # Include the pathIdx and path sets
    ampl.set['pathIdx'] = path_idxs
    for path_idx in path.keys():
        ampl.set['path'][path_idx] = path[path_idx]['link_ids']


def fill_service(ampl: AMPL, infra: nx.classes.graph.Graph,
                 config: dict) -> None:
    """Fills the model with the service-related sets and parameters

    :ampl: AMPL: instance of the model with filled information 
    :infra: nx.classes.graph.Graph: infrastructure graph
    :config: dict: configuration dictionary
    :returns: None

    """
    ampl.set['services'] = [s['id'] for s in config['services']]
    locations = []
    owners = {}
    serv_vnfs = {}
    radio_vnfs = {}
    vnf_radio_techs = {}
    max_instances = {}
    life_time_start = {}
    life_time_end = {}
    service_locs = {}
    endpoint_services = {}
    vnf_time = {}

    for s in config['services']:
        service_gml = None
        service_locs[s['id']] = []

        # Init service vnfs dictionary for this service
        if s['id'] not in serv_vnfs:
            serv_vnfs[s['id']] = []

        # Service lifetime
        if 'lifeTimeStart' in s:
            life_time_start[s['id']] = s['lifeTimeStart']
        if 'lifeTimeEnd' in s:
            life_time_end[s['id']] = s['lifeTimeEnd']

        service_g = nx.read_gml(s['graph'], label='id')

        # Locations and vnfs
        for node,d in service_g.nodes(data=True):
            if d['type'] == 'vnf':
                serv_vnfs[s['id']] += [d['name']]
                vnf_time[d['name']] = d['vnfTime']
            elif d['type'] == 'endpoint':
                endpoint_services[d['name']] = s['id']
            if 'maxInstances' in d:
                max_instances[(d['name'], s['id'])] = d['maxInstances']
            if d['radio'] != "":
                radio_vnfs[s['id']] = [d['name']]
                if d['type'] == 'vnf' and\
                   (d['radio'], d['name']) not in vnf_radio_techs:
                    vnf_radio_techs[d['radio'], d['name']] = 1

            if 'lon' in d and 'lat' in d:
                service_locs[s['id']].append('(' + str(d['lon']) + ',' +\
                                             str(d['lat']) + ')')
        locations += service_locs[s['id']]

        # Associate service to its owner
        if s['owner'] not in owners:
            owners[s['owner']] = [s['id']]
        else:
            owners[s['owner']] += [s['id']]


    # Add the services lifetime start and end
    df = DataFrame('services', 'lifetimeS')
    df.setValues(life_time_start)
    ampl.setData(df)
    df = DataFrame('services', 'lifetimeE')
    df.setValues(life_time_end)
    ampl.setData(df)

    # Add the locations
    ampl_locs = ampl.getSet('locations')
    ampl_locs = [] if ampl_locs.size() == 0 else ampl_locs.getValues()
    locations = list(filter(lambda l: l not in ampl_locs, locations))
    ampl.set['locations'] = list(set(ampl_locs).union(set(locations)))

    # Add the services used by each endpoint
    df = DataFrame('endpoints', 'serviceE')
    df.setValues(endpoint_services)
    ampl.setData(df)

    # Add the services' locations
    for service,serviceLocs in service_locs.items():
        ampl.set['serviceLocs'][service] = list(set(serviceLocs))

    # Choose which locations are covered by radio enabled nodes
    df = DataFrame(('cNodes', 'locations'), 'covered')
    covered = {}
    for _,n in filter(lambda n: n[1]['radio'] != '', infra.nodes(data=True)):
        for loc in locations:
            loc_coords = tuple(map(lambda c: float(c), loc[1:-1].split(',')[::-1]))
            if haversine(loc_coords, (n['lat'], n['lon']), unit='m') <\
                    config['coverageDistance'][n['radio']]:
                covered[(n['name'], loc)] = 1
    df.setValues(covered)
    ampl.setData(df)
    
    # Add new owners 
    ampl_owners = ampl.set['owners']
    ampl_owners = [] if ampl_owners.size() == 0 else ampl_owners.getValues()
    owners_names = list(filter(lambda o: o not in ampl_owners, owners.keys()))
    ampl.set['owners'] = list(set(ampl_owners).union(set(owners_names)))

    # Add the owners' new services
    o_servs = ampl.getSet('oServices')
    for owner,o_servs in ampl.getSet('oServices').instances():
        if owner not in owners and o_servs.size() > 0:
            owners[owner] = o_servs
    for owner,o_services in owners.items():
        ampl.set['oServices'][owner] = o_services


    # Add the new vnfs
    vnfs = [] if ampl.set['vnfs'].size() == 0 else ampl.set['vnfs']
    for service in serv_vnfs:
        vnfs += serv_vnfs[service]
    ampl.set['vnfs'] = list(set(vnfs))

    # Add new service vnfs
    ampl_serv_vnfs = ampl.getSet('sVnfs')
    for service,s_vnfs in ampl.set['sVnfs'].instances():
        if service not in serv_vnfs and s_vnfs.size() > 0:
            serv_vnfs[service] = s_vnfs.getValues()
        elif s_vnfs.size() > 0:
            ampl_vnfs = [v for v in s_vnfs.getValues()\
                                 if v not in serv_vnfs[service]]
            serv_vnfs[service] += ampl_vnfs
    for service,s_vnfs in serv_vnfs.items():
        ampl.set['sVnfs'][service] = list(set(s_vnfs))

    # Add new service radio vnfs
    for service,r_vnfs in ampl.set['rVnfs'].instances():
        if service not in radio_vnfs and r_vnfs.size() > 0:
            radio_vnfs[service] = r_vnfs.getValues()
        elif r_vnfs.size() > 0:
            radio_vnfs[service] += [v for v in r_vnfs.getValues()\
                                            if v not in radio_vnfs[service]]
    for service,r_vnfs in radio_vnfs.items():
        ampl.set['rVnfs'][service] = r_vnfs

    # Add the radio technologies
    radio_techs = [] if len(list(ampl.set['radioTechs'])) == 0\
                     else list(ampl.set['radioTechs'].members())
    radio_techs += list(map(lambda rt: rt[0], vnf_radio_techs.keys()))
    ampl.set['radioTechs'] = list(set(radio_techs))

    # Set which radio technology has each VNF
    df = DataFrame(('radioTechs', 'vnfs'), 'radioVnf')
    df.setValues(vnf_radio_techs)
    ampl.setData(df)

    # Set the maximum number of instances
    df = DataFrame(('vnfs', 'services'), 'maxInstances')
    df.setValues(max_instances)
    ampl.setData(df)

    # Set the average processing time of a VNF
    df = DataFrame('vnfs', 'vnfTime')
    df.setValues(vnf_time)
    ampl.setData(df)


def fill_service_traffic(ampl: AMPL, infra: nx.classes.graph.Graph,
                         config: dict) -> None:
    """Fills the model with the service traffic-related parameters

    :ampl: AMPL: instance of the model with filled information 
    :infra: nx.classes.graph.Graph: infrastructure graph
    :config: dict: configuration dictionary
    :returns: None

    """
    for s in config['services']:
        service_g = nx.read_gml(s['graph'], label='id')

        # Retrieve service trails
        service_trails = []
        start_ids = [vi for vi,v in service_g.nodes(data=True)\
                                 if v['name'] in s['startEndpoints']]
        finish_ids = [vi for vi,v in service_g.nodes(data=True)\
                                  if v['name'] in s['finishvNodes']]
        for start_id in start_ids:
            service_trails += list(get_all_trails(G=service_g, source=start_id,
                                                  target=finish_ids))

        # Fill the chi-s
        chi = {}
        for v,v_d in service_g.nodes(data=True):
            if v_d['type'] != 'vnf':
                continue
            in_traffic = 0
            for v_prev,_,vl in service_g.in_edges(v, data=True):
                in_traffic += vl['bandwidth']

            # next neighbors chi(prev,v,next) = (v,next)[bw]/in_traffic
            for _,v_next,vl in service_g.out_edges(v, data=True):
                v_n_i = service_g.nodes[v_next]['name']
                for v_prev,_ in service_g.in_edges(v):
                    v_p_i = service_g.nodes[v_prev]['name']
                    chi[(v_p_i, v_d['name'], v_n_i)] = vl['bandwidth'] /\
                                                       in_traffic
        
        df = DataFrame(('vNodes', 'vnfs', 'vNodes_finish'), 'chi')
        df.setValues(chi)
        ampl.setData(df)

        # Fill first flows
        flow = {}
        for v1,v2,vl in service_g.edges(data=True):
            if service_g.nodes[v1]['type'] != 'vnf':
                continue
            for e,e_d in [(e,d) for e,d in service_g.nodes(data=True)\
                                      if d['name'] in s['startEndpoints']]:
                if e_d['type'] != 'endpoint':
                    continue
                
                # Check if (e,v1,v1) or (e,v1,v2) exists
                vl_in_e_flow = False
                first_v_in_e_flow = False
                for service_trail in service_trails:
                    paired_trail = list(zip(service_trail, service_trail[1:]))
                    vl_in_e_flow = vl_in_e_flow or (e in service_trail and\
                                                    (v1,v2) in paired_trail)
                    first_v_in_e_flow = first_v_in_e_flow or ((e,v1) in\
                                                              paired_trail)

                # Store the flows' information
                e_nm = service_g.nodes[e]['name']
                v1_nm = service_g.nodes[v1]['name']
                v2_nm = service_g.nodes[v2]['name']
                if vl_in_e_flow:
                    flow[(e_nm,v1_nm,v2_nm)] = vl['bandwidth']
                if first_v_in_e_flow:
                    flow[(e_nm,v1_nm,v1_nm)] = service_g[e][v1]['bandwidth']

        df = DataFrame(('endpoints', 'vnfs', 'vNodes'), 'flow')
        df.setValues(flow)
        ampl.setData(df)


def create_dat(ns: nx.classes.graph.Graph, infra: nx.classes.graph.Graph,
        model_path: str, config: dict, dat_path: str) -> None:
    """Creates the .dat file filled with the network service and infrastructure
    graphs

    :ns: nx.classes.graph.Graph: networkx instance with the network service
    graph
    :infra: nx.classes.graph.Graph: networkx instance with the physical graph
    :model_path: str: path to the system_model.mod file
    :config: dict: configuration dictionary
    :dat_path: str: path to the data.dat file to store the scenario data
    :returns: None

    """
    ampl = AMPL()
    ampl.read(model_path)
    ampl.param['endTime'] = config['endTime']
    fill_phy_nodes(ampl, infra, config)
    fill_links(ampl, infra, config)
    fill_paths(ampl, infra, config)
    fill_service(ampl, infra, config)
    fill_service_traffic(ampl, infra, config)
    ampl.exportData(datfile=dat_path)
    
    # Remove auxiliary sets and parameters
    with open(dat_path, "r+") as f:
        lines = f.readlines()
        f.seek(0)
        for line in lines:
            if re.search('set phyLink\[', line) == None and\
               re.search('set vNodes', line) == None and\
               re.search('set phyNodes', line) == None:
                f.write(line)
        f.truncate()




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Given network service and' +\
            ' infrastructure graphs, it creates an AMPL .dat file')
    parser.add_argument('ns', metavar='ns', type=str,
                        help='Path to the network service GML file')
    parser.add_argument('infra', metavar='infra', type=str,
                        help='Path to the infrastructure GML file')
    parser.add_argument('model', metavar='model', type=str,
                        help='Path to the AMPL model')
    parser.add_argument('config', metavar='config', type=str,
                        help="Path to the JSON configuration file")
    parser.add_argument('out', metavar='out', type=str,
                        help='Path to the output where .dat is created')
    args = parser.parse_args()

    # Read .gml files of the network service and infrastructure graphs
    # ns = nx.read_gml(path=args.ns)
    infra = nx.read_gml(path=args.infra, label='id')

    config = None
    with open(args.config, 'r') as f:
        config = json.load(f)


    if not check_endpoint_locs(infra, config):
        sys.exit(1)
    create_dat(ns=infra, infra=infra, model_path=args.model, config=config,
                dat_path=args.out)


