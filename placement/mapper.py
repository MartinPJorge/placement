from abc import ABCMeta, abstractmethod
from haversine import haversine
import copy
import networkx as nx
import sys
import re
import logging
from itertools import islice
from checker import AbstractChecker, CheckFogDigraphs
from functools import reduce
from utils import k_shortest_paths
from math import log

class AbstractMapper(metaclass=ABCMeta):

    """Abstract class for Mappers that perform VNF placements"""

    @abstractmethod
    def __init__(self, checker: AbstractChecker):
        """Inits the mapper with its associated graphs checker

        :checker: AbstractChecker: instance of a graph checker
        :returns: None

        """
        self.__checker = checker


    @abstractmethod
    def map(self, infra, ns) -> dict:
        """Maps a network service on top of an infrastructure.

        :infra: infrastructure graph
        :ns: network service graph
        :returns: dict: mapping decissions dictionary

        """
        pass


class GreedyCostMapper(AbstractMapper):

    """Mapper to minimize cost of placing the network service.
       It traverses the network service graph node by node, deciding at each
       step the mapping of the node and the edge that connects it with the
       next one. That is, it follows a greedy approach."""


    def __init__(self, checker: AbstractChecker, k: int):
        """Initializes a Greedy Cost mapper

        :checker: AbstractChecker: instance of a graph checker
        :k: int: k shortest paths parameter for the virtual links steering

        """
        self.__checker = checker
        self.__k = k


    def __get_host(self, vnf, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph):
        """Retrieve cheapest host in the infrastructure to place the vnf.

        :vnf: vnf identifier
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: identifier of best host

        """
        best_host, best_cost = None, sys.maxsize

        # Filter RAT capable hosts
        hosts = list(infra.nodes())
        if 'rats' in ns.nodes[vnf]:
            hosts = list(filter(lambda h: 'rats' in infra.nodes[h], hosts))
            for h in hosts:
                hosts = [h for h in hosts if reduce(lambda rv1,rv2: rv1 or rv2,
                map(lambda rv: rv in infra.nodes[h]['rats'],
                    ns.nodes[vnf]['rats']))]
        else:
            hosts = filter(lambda h: 'rats' not in infra.nodes[h], hosts)

        # Filter hosts by location constraint
        if 'location' in ns.nodes[vnf]:
            vloc = ns.nodes[vnf]['location']['center']
            vrad = ns.nodes[vnf]['location']['radius']
            hosts = filter(lambda h: 'location' in infra.nodes[h]\
                    and haversine(infra.nodes[h]['location'], vloc) <= vrad,
                    hosts)

        for host in hosts:
            host_cpu = infra.nodes[host]['cpu']
            host_mem = infra.nodes[host]['mem']
            host_disk = infra.nodes[host]['disk']
            host_cost = infra.nodes[host]['cost']

            if host_cpu >= ns.nodes[vnf]['cpu'] and\
                    host_mem >= ns.nodes[vnf]['mem'] and\
                    host_disk >= ns.nodes[vnf]['disk']:

                host_cost_n = host_cost['cpu'] * ns.nodes[vnf]['cpu'] +\
                        host_cost['mem'] * ns.nodes[vnf]['mem'] +\
                        host_cost['disk'] * ns.nodes[vnf]['disk']
                
                if host_cost_n < best_cost:
                    best_host = host
                    best_cost = host_cost_n
        
        return best_host


    def __get_path(self, vl, src_host, dst_host,
            infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> dict:
        """Obtains a path to steer the vl accross the infrastructure,
        satisfying bandwidth and delay constraints.
        It looks for the cheapest path.

        :vl: tuple of VNF identifiers (v1,v2)
        :src_host: identifier of the host where the vl starts
        :dst_host: identifier of the host where the vl ends 
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: dict: {'cost', 'path': [h1, ..., hn]}, or {} if fails

        """
        # Prune links not meeting bandwidth and delay requirements
        vl = ns[vl[0]][vl[1]]
        pruned_infra = copy.deepcopy(infra)
        pruned_links = [(h1,h2) for h1,h2 in pruned_infra.edges()\
                if pruned_infra[h1][h2]['bw'] < vl['bw'] or\
                    pruned_infra[h1][h2]['delay'] > vl['delay']]
        pruned_infra.remove_edges_from(pruned_links)

        all_shortest = nx.all_shortest_paths(pruned_infra,
                src_host, dst_host, weight='cost')
        best_path, best_cost = None, sys.maxsize
        for path in islice(all_shortest, self.__k):
            cost, delay = 0, 0
            for h1,h2 in zip(path, path[1:]):
                cost += infra[h1][h2]['cost']
                delay += infra[h1][h2]['delay']

            if delay < vl['delay'] and cost < best_cost:
                best_cost = cost
                best_path = path

        return {'cost': best_cost, 'path': best_path} if best_path else {}


    def __consume_vnf(self, host, vnf, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> None:
        """Consumes host's resources based on vnf resources

        :host: host identifier
        :vnf: vnf identifier within the graph
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: None

        """
        infra.nodes[host]['cpu'] -= ns.nodes[vnf]['cpu']
        infra.nodes[host]['mem'] -= ns.nodes[vnf]['mem']
        infra.nodes[host]['disk'] -= ns.nodes[vnf]['disk']


    def __consume_vl(self, path: list, vl, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> None:
        """Consumes the vl bandwidth accross the given path

        :path: list: list of host id tuples [(h1,h2), ...]
        :vl: tuple of VNF identifiers (vnf1Id, vnf2Id)
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: None

        """
        for h1,h2 in zip(path, path[1:]):
            infra[h1][h2]['bw'] -= ns[vl[0]][vl[1]]['bw']


    def map(self, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> dict:
        """Maps a network service on top of an infrastructure.

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: dict: mapping decissions dictionary

        """
        mapping = {
            'worked': True
        }

        # Check that graphs have correct format
        if not self.__checker.check_infra(infra) or\
                not self.__checker.check_ns(ns):
            mapping['worked'] = False
            return mapping

        infra_tmp = copy.deepcopy(infra)
        for vl in ns.edges():
            # Map the VNFs
            vnf1, vnf2 = vl
            for vnf in set(vl).difference(set(mapping.keys())):
                host = self.__get_host(vnf=vnf, infra=infra_tmp, ns=ns)
                if not host:
                    mapping['worked'] = False
                    return mapping
                else:
                    mapping[vnf] = host
                    self.__consume_vnf(host, vnf, infra_tmp, ns)

            # Map the VL
            vl_map = self.__get_path(vl=vl, src_host=mapping[vnf1],
                    dst_host=mapping[vnf2], infra=infra_tmp, ns=ns)
            if vl_map == {}:
                mapping['worked'] = False
                return mapping
            mapping[vl] = vl_map['path']
            self.__consume_vl(path=vl_map['path'], vl=vl,
                    infra=infra_tmp, ns=ns)
    
        return mapping



class GreedyFogCostMapper(AbstractMapper):

    """Class definition of a mapper that greedily minimizes costs while
    accounting for reliability and service lifetime."""


    def __init__(self, checker: CheckFogDigraphs, k: int):
        """Initializes a Greedy Fog cost mapper

        :checker: CheckFogDigraphs: instance of a fog graph checker
        :k: int: k shortest paths parameter for the virtual links steering

        """
        self.__checker = checker
        self.__k = k


    def __consume_vnf(self, host, vnf, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> None:
        """Consumes host's resources based on vnf resources

        :host: host identifier
        :vnf: vnf identifier within the graph
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: None

        """
        infra.nodes[host]['cpu'] -= ns.nodes[vnf]['cpu']
        infra.nodes[host]['mem'] -= ns.nodes[vnf]['mem']
        infra.nodes[host]['disk'] -= ns.nodes[vnf]['disk']


    def __consume_vl(self, path: list, vl, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> None:
        """Consumes the vl bandwidth accross the given path

        :path: list: list of host id tuples [(h1,h2), ...]
        :vl: tuple of VNF identifiers (vnf1Id, vnf2Id)
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: None

        """
        for h1,h2 in zip(path, path[1:]):
            infra[h1][h2]['bw'] -= ns[vl[0]][vl[1]]['bw']


    def __better_host(self, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph, vnf, host_a, host_b) -> bool:
        """Determines if host_a is better than host_b to deploy VNF vnf,
        attending to following priorities
            1. lifetime
            2. reliability
            3. cost

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :vnf: vnf identifier
        :host_a: identifier of host A
        :host_b: identifier of host B (None accepted)
        :returns: True/False if host A is better than host B

        """
        if host_b == None:
            return True
        
        # If lifetimes differ, return lifetime_a > lifetime_b
        la_lb = infra.nodes[host_a]['lifetime'] -\
                infra.nodes[host_b]['lifetime']
        if la_lb != 0:
            return la_lb > 0

        # If reliabilities differ, return reliability_a > reliability_b
        ra_rb = infra.nodes[host_a]['reliability'] -\
                infra.nodes[host_b]['reliability']
        if ra_rb != 0:
            return ra_rb > 0

        # Determine the deployment cost of the VNF
        costs = []
        for host in [host_a, host_b]:
            cost = infra.nodes[host]['cost']['cpu'] * ns.nodes[vnf]['cpu'] +\
                   infra.nodes[host]['cost']['disk'] * ns.nodes[vnf]['disk'] +\
                   infra.nodes[host]['cost']['mem'] * ns.nodes[vnf]['mem']
            costs.append(cost)

        # If costs differ, return cost_a > cost_b
        ca_cb = costs[0] - costs[1]
        if ca_cb != 0:
            return ca_cb < 0
    
        return False # they are both equally good


    def __get_host(self, vnf, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph):
        """Retrieve the best host attending to following priorities (descendent
        order):
            1. lifetime
            2. reliability
            3. cost

        :vnf: vnf identifier
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: identifier of best host

        """
        best_host = None

        # Filter RAT capable hosts
        hosts = list(infra.nodes())
        if 'rats' in ns.nodes[vnf]:
            hosts = list(filter(lambda h: 'rats' in infra.nodes[h], hosts))
            for h in hosts:
                hosts = [h for h in hosts if reduce(lambda rv1,rv2: rv1 or rv2,
                map(lambda rv: rv in infra.nodes[h]['rats'],
                    ns.nodes[vnf]['rats']))]
        else:
            hosts = filter(lambda h: 'rats' not in infra.nodes[h], hosts)

        # Filter hosts by location constraint
        if 'location' in ns.nodes[vnf]:
            vloc = ns.nodes[vnf]['location']['center']
            vrad = ns.nodes[vnf]['location']['radius']
            hosts = filter(lambda h: 'location' in infra.nodes[h]\
                    and haversine(infra.nodes[h]['location'], vloc) <= vrad,
                    hosts)


        # Find the best fog host
        for host in hosts:
            if infra.nodes[host]['cpu'] >= ns.nodes[vnf]['cpu'] and\
               infra.nodes[host]['mem'] >= ns.nodes[vnf]['mem'] and\
               infra.nodes[host]['disk'] >= ns.nodes[vnf]['disk'] and\
               self.__better_host(infra, ns, vnf, host, best_host):
                best_host = host

        return best_host


    def __get_path(self, vl, src_host, dst_host,
                   infra: nx.classes.digraph.DiGraph,
                   ns: nx.classes.digraph.DiGraph) -> dict:
        """Obtains a path to steer the vl accross the infrastructure,
        satisfying bandwidth and delay constraints.
        It looks for the cheapest, most reliable path, i.e., this is the
        descendent list of priorities:
            1. reliability
            2. cost

        :vl: tuple of VNF identifiers (v1,v2)
        :src_host: identifier of the host where the vl starts
        :dst_host: identifier of the host where the vl ends 
        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: dict: {'cost', 'reliability', 'path': [h1, ..., hn]},
                  or {} if fails

        """
        # Prune links not meeting bandwidth and delay requirements
        vl = ns[vl[0]][vl[1]]
        pruned_infra = copy.deepcopy(infra)
        pruned_links = [(h1,h2) for h1,h2 in pruned_infra.edges()\
                if pruned_infra[h1][h2]['bw'] < vl['bw'] or\
                    pruned_infra[h1][h2]['delay'] > vl['delay']]
        pruned_infra.remove_edges_from(pruned_links)

        # Set the graph weight as 1/link_reliability
        weights = {(h1,h2): 1 / d['reliability']
                   for (h1,h2,d) in pruned_infra.edges(data=True)}
        nx.set_edge_attributes(pruned_infra, name='inv_reliab', values=weights)

        # Get the cheapest path among the most reliables
        all_shortest = nx.all_shortest_paths(pruned_infra,
                src_host, dst_host, weight='inv_reliab')
        best_path, best_reliab, best_cost = None, 0, sys.maxsize
        for path in islice(all_shortest, self.__k):
            cost, delay, reliab = 0, 0, 1
            for h1,h2 in zip(path, path[1:]):
                cost += infra[h1][h2]['cost']
                reliab *= infra[h1][h2]['reliability']
                delay += infra[h1][h2]['delay']

            if delay < vl['delay']:
                if reliab > best_reliab or\
                   reliab == best_reliab and cost < best_cost:
                    best_reliab = reliab
                    best_cost = cost
                    best_path = path


        return {'cost': best_cost, 'path': best_path,
                'reliability': best_reliab} if best_path else {}


    def map(self, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph) -> dict:
        """Maps a network service on top of an infrastructure.

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: dict: mapping decissions dictionary

        """
        mapping = {
            'worked': True
        }

        # Check that graphs have correct format
        if not self.__checker.check_infra(infra) or\
                not self.__checker.check_ns(ns):
            mapping['worked'] = False
            return mapping

        infra_tmp = copy.deepcopy(infra)
        for vl in ns.edges():
            # Map the VNFs
            vnf1, vnf2 = vl
            for vnf in set(vl).difference(set(mapping.keys())):
                host = self.__get_host(vnf=vnf, infra=infra_tmp, ns=ns)
                if not host:
                    mapping['worked'] = False
                    return mapping
                else:
                    mapping[vnf] = host
                    self.__consume_vnf(host, vnf, infra_tmp, ns)

            # Map the VL
            vl_map = self.__get_path(vl=vl, src_host=mapping[vnf1],
                    dst_host=mapping[vnf2], infra=infra_tmp, ns=ns)
            if vl_map == {}:
                mapping['worked'] = False
                return mapping
            mapping[vl] = vl_map['path']
            self.__consume_vl(path=vl_map['path'], vl=vl,
                    infra=infra_tmp, ns=ns)
    
        return mapping


    @staticmethod
    def map_reliability(infra: nx.classes.digraph.DiGraph,
                        mapping: dict) -> float:
        """Retrieve the reliability of a ns mapping

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :path: dict: mapping decissions dictionary
        :returns: the reliability

        """
        reliab = 1

        # Multiply by hosts reliability
        for vnf in [k for k in mapping.keys()\
                    if k != 'worked' and type(k) != tuple]:
            reliab *= infra.nodes[mapping[vnf]['host']]['reliability']

        # Multiply by links' reliability
        for vl in [k for k in mapping.keys()\
                   if k != 'worked' and type(k) == tuple]:
            limits = [mapping[vl][0], mapping[vl][-1]]
            for h1,h2 in zip(mapping[vl][:-1], mapping[vl][1:]):
                if h1 not in limits:
                    reliab *= infra.nodes[h1]['reliability']
                if h2 not in limits:
                    reliab *= infra.nodes[h2]['reliability']

                reliab *= infra[h1][h2]['reliability']

        return reliab


    @staticmethod
    def map_lifetime(infra: nx.classes.digraph.DiGraph,
                     mapping: dict) -> float:
        """Retrieves the lifetime of a mapping

        :infra: nx.classes.digraph.DiGraph: inftastructure digraph instance 
        :mapping: dict: dictionary with the result of map() method
        :returns: the minimum lifetime accross the mapped path

        """
        lifetime = 0

        return min([infra.nodes[mapping[k]]['lifetime']\
                    for k in mapping.keys()\
                    if k != 'worked' and type(k) != tuple])

        
    @staticmethod
    def map_cost(infra: nx.classes.digraph.DiGraph,
                 ns: nx.classes.digraph.DiGraph, mapping: dict) -> float:
        """Retrieves the cost of a given mapping

        :infra: nx.classes.digraph.DiGraph: infrastructure digraph instance
        :ns: nx.classes.digraph.DiGraph: network service graph
        :mapping: dict: dictionary with the result of map() method
        :returns: cost of the given mapping

        """
        cost = 0

        # VNF mapping cost
        for vnf in [k for k in mapping.keys() if type(k) != tuple and\
                                                 k != 'worked']:
            for r in infra.nodes[mapping[vnf]]['cost'].keys():
                cost += infra.nodes[mapping[vnf]]['cost'][r] * ns.nodes[vnf][r]

        # VL mapping cost
        for vl in [k for k in mapping.keys() if type(k) == tuple]:
            for h1,h2 in zip(mapping[vl], mapping[vl][1:]):
                cost += infra[h1][h2]['cost'] * ns[vl[0]][vl[1]]['bw']

        return cost


    @staticmethod
    def map_delay(infra: nx.classes.digraph.DiGraph,
                  ns: nx.classes.digraph.DiGraph, mapping: dict) -> float:
        """Retrieve the delay of the mapped network service

        :infra: nx.classes.digraph.DiGraph: infrastructure digraph instance
        :ns: nx.classes.digraph.DiGraph: network service graph
        :mapping: dict: dictionary with the result of map() method
        :returns: delay of the given mapping

        """
        delay = 0
        
        for vl in [k for k in mapping.keys() if type(k) == tuple]:
            for h1,h2 in zip(mapping[vl], mapping[vl][1:]):
                delay += infra[h1][h2]['delay']

        return delay


class FPTASMapper(AbstractMapper):
    DELAY_FACTOR = 1/129

    """Maps a network service using a FPTAS modification of multiconstraint
       routing under path additive constraints. Algorithm 2 of [1]
       
       [1] Xue, Guoliang, et al. "Finding a path subject to many additive QoS
       constraints."
       IEEE/ACM Transactions on Networking (TON) 15.1 (2007): 201-211."""


    def __init__(self, checker: CheckFogDigraphs, log_out: str = 'aux_g.loh'):
        """Inits the mapper with its associated graphs checker

        :checker: CheckFogDigraph: instance of a fog graph checker
        :log_out: str: file to output the log of the mapper
        :returns: None

        """
        self.__checker = checker
        self.__log = logging.getLogger(name=log_out)
        file_handler = logging.FileHandler(log_out, mode='w')
        self.__log.addHandler(file_handler)


    def __build_aux(self, infra: nx.classes.digraph.DiGraph, src,
                    k: int, tau: int, ereliab: float)\
                            -> nx.classes.digraph.DiGraph:
        """Creates a digraph with nodes connected directly through paths

        :infra: nx.classes.digraph.DiGraph: infrastructure digraph
        :src: id of the source node used to build the auxiliary graph
        :k: int: number of shortest paths between computational nodes
        :tau: int: granularity, the higher, the more precise
        :ereliab: float: endpoint reliability
        :returns: nx.classes.digraph.DiGraph

        """
        self.__log.info('enter build auxiliary graph')
        comp_nodes = set([n for n in infra.nodes()\
                            if ('cpu' in infra.nodes[n] and
                                infra.nodes[n]['cpu'] > 0) or\
                                'endpoint' in infra.nodes[n] and\
                                infra.nodes[n]['endpoint']])
        if src not in comp_nodes:
            comp_nodes.union(src)
        src_paths = {}

        # Find all paths between computational nodes
        self.__log.info('finding all paths between nodes')
        for from_ in comp_nodes:
            src_paths[from_] = {}
            #for to_ in [c for c in comp_nodes if c != from_]:
            for to_ in comp_nodes:
                if not nx.has_path(infra, from_, to_):
                    continue
                for path in k_shortest_paths(infra, from_, to_,
                                             k=k, weight='delay'):
                    if to_ not in src_paths[from_]:
                        src_paths[from_][to_] = {
                            'paths': [],
                            'delays': [],
                            'reliability': [],
                            'bw': [],
                            'cost': []
                        }

                    # Calculate path delay and reliability
                    src_paths[from_][to_]['paths'] += [path]
                    delay, reliab, cost, bw = 0, 1, 0, float('inf')
                    for (n1,n2) in zip(path[:-1], path[1:]):
                        if infra[n1][n2]['bw'] < bw:
                            bw = infra[n1][n2]['bw']
                        delay += infra[n1][n2]['delay']
                        reliab *= infra[n1][n2]['reliability']
                        if n2 != to_:
                            reliab *= infra.nodes[n2]['reliability']
                        cost += infra[n1][n2]['cost']
                    src_paths[from_][to_]['delays'] += [delay]
                    src_paths[from_][to_]['reliability'] += [reliab]
                    src_paths[from_][to_]['bw'] += [bw]
                    src_paths[from_][to_]['cost'] += [cost]


        # Build the auxiliary graph
        self.__log.info('inserting (c,A) nodes in the auxiliary graph')
        self.__aux_g = nx.DiGraph()
        for comp_node in comp_nodes:
            for tau_ in range(tau + 1):
                self.__aux_g.add_node((comp_node,tau_),
                                      **infra.nodes[comp_node])

        # Connect the auxiliary graph nodes
        self.__log.info('connect nodes (c,A)--(c2,B) of auxiliary nodes')
        for (c1,A) in self.__aux_g.nodes():
            for (c2,B) in self.__aux_g.nodes():
                if not nx.has_path(infra, c1, c2):
                    continue
                best_idx = src_paths[c1][c2]['reliability'].index(\
                                min(src_paths[c1][c2]['reliability']))
                w1 = -1 * tau * log(1 /\
                        (src_paths[c1][c2]['reliability'][best_idx]*\
                                infra.nodes[c2]['reliability'])) /\
                            log(ereliab)
                if A + w1 <= B:
                    self.__aux_g.add_edge((c1,A), (c2,B), w1=w1,
                                delay=src_paths[c1][c2]['delays'][best_idx],
                                path=src_paths[c1][c2]['paths'][best_idx],
                                bw=src_paths[c1][c2]['bw'][best_idx],
                                cost=src_paths[c1][c2]['cost'][best_idx])


    @staticmethod
    def ordered_vls(ns: nx.classes.digraph.DiGraph) -> list:
        """Obtain the ordered list of virtual links in a network service

        :ns: nx.classes.digraph.DiGraph:  network service graph
        :returns: list: [(vnf1, vnf2, {...}), ...]

        """
        start_vnf = list(filter(lambda vnf: ns.in_degree(vnf) == 0,
                                ns.nodes()))[0]
        curr_vnf = start_vnf
        vls = []
        while len(ns[curr_vnf]) > 0:
            next_vnf = list(ns[curr_vnf])[0]
            vls += [(curr_vnf, next_vnf, ns[curr_vnf][next_vnf])]
            curr_vnf = next_vnf

        return vls


    def __get_mapping(self, c_f, A_f: int, prev: dict, assigned_cpu: dict,
                      vls: list):
        """Gets the mapping derived from the mapping.

        :c_f: last physical node ID
        :A_f: int: tau parameter of the last physical node
        :prev: dict: dictionary of previous physical nodes
        :assigned_cpu: dict: dictionary of cpu assigned to each VNF
        :vls: list: ordered list of virtual links
        :returns: dictionary with the mappings

        """
        self.__log.info('translating (c_f,A_f) into a mapping')
        curr_c, curr_A = c_f, A_f
        mapping = {}

        for vl in vls[::-1]:
            c_0, A_0 = prev[(curr_c,curr_A,vl[0],vl[1])]
            mapping[vl[0],vl[1]] = self.__aux_g[(c_0,A_0)][(curr_c,curr_A)]\
                                                ['path']
            mapping[vl[1]] = {
                'host': curr_c,
                'cpu': assigned_cpu[(curr_c,curr_A,vl[0],vl[1])]
            }
            curr_c, curr_A = c_0, A_0

        return mapping


    def __loc_rat_capable(self, infra: nx.classes.digraph.DiGraph,
                          ns: nx.classes.digraph.DiGraph, vnf, host):
        """Tells if a host satisfies the location and RAT constraints of a VNF

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :vnf: identifier of the vnf
        :host: identifier of the host
        :returns: boolean

        """
        # Check location constraints
        if 'location' in ns.nodes[vnf] and ns.nodes[vnf]['location'] != None:
            if 'location' not in infra.nodes[host] or\
                    infra.nodes[host]['location'] == None:
                return False
            else:
                vnf_coords = (ns.nodes[vnf]['location']['center'][0],
                              ns.nodes[vnf]['location']['center'][1])
                host_coords = (infra.nodes[host]['location'][0],
                               infra.nodes[host]['location'][1])
                if haversine(vnf_coords, host_coords) >\
                        ns.nodes[vnf]['location']['radius']:
                    return False

        # Check RAT constraints
        if 'rats' in ns.nodes[vnf] and ns.nodes[vnf]['rats'] != None:
            if 'rats' not in infra.nodes[host] or\
                    infra.nodes[host]['rats'] == None:
                return False
            elif not all(map(lambda v_rat: v_rat in infra.nodes[host]['rats'],
                             ns.nodes[vnf]['rats'])):
                return False

        return True 


    def map(self, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph, k: int, tau: int,
            relax: int) -> dict:
        """Maps a network service using a variation of [1]

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :k: int: number of shortest paths between computational nodes
        :tau: int: granularity, the higher, the more precise
        :relax: int: delay relaxation per virtual link, high value=high relax
        :returns: dict: mapping decissions dictionary

        """
        endpoint = list(filter(lambda vnf: ns.in_degree(vnf) == 0,
                               ns.nodes()))[0]
        self.__build_aux(infra=infra, src=endpoint, k=k, tau=tau,
                         ereliab=ns.nodes[endpoint]['reliability'])
        self.__log.info('setting auxiliary variables')
        vls = FPTASMapper.ordered_vls(ns)
        hop_delay = [ns.nodes[endpoint]['delay']/len(ns.edges)] * len(ns.edges)

        # Dictionaries to store cost and cpu as mapping advances
        cost = {
            (c,A,v1,v2): float('inf')
            for c,A in self.__aux_g.nodes()
            for v1,v2,_ in vls
        }
        curr_cpu = {
            (c,A,v1,v2): infra.nodes[c]['cpu']
            for c,A in self.__aux_g.nodes()
            for v1,v2,_ in vls
        }
        needed_cpu = {
            (c,A,v1,v2): 0
            for c,A in self.__aux_g.nodes()
            for v1,v2,_ in vls
        }
        prev = {
            (c,A,v1,v2): None
            for c,A in self.__aux_g.nodes()
            for v1,v2,_ in vls
        }

        # MAIN LOOP
        # Note: in lambdas C0=(c0,A)
        hop = 0
        self.__log.info('entering main loop')
        while hop < len(vls):
            relaxed = 0
            v1,v2,vl_d = vls[hop]
            v0, first_vl = (None,True) if hop == 0 else (vls[hop-1][0],False)
            self.__log.info('mapping virtual link (' + str(v1) + ',' +\
                            str(v2) + ')')

            to_visit = self.__aux_g.edges(data=True) if not first_vl else\
                       filter(lambda e: e[0][0] == endpoint and e[0][1] == 0,
                              self.__aux_g.edges(data=True))


            for ((c1,A),(c2,B),l_d) in filter(lambda e:\
                                            e[2]['bw'] >= vl_d['bw'], to_visit):
                need_cpu = FPTASMapper.DELAY_FACTOR * vl_d['bw'] /\
                           (1 - ns.nodes[v2]['lv'] /\
                                   (hop_delay[hop] - l_d['delay'])) if\
                             l_d['delay'] < hop_delay[hop] else float('inf')
                incur_cost = infra.nodes[c2]['cost']['cpu'] * need_cpu +\
                             self.__aux_g[(c1,A)][(c2,B)]['cost'] *vl_d['bw']+\
                             (0 if first_vl else cost[(c1,A,v0,v1)])

                if curr_cpu[(c2,B,v1,v2)] >= need_cpu and\
                        incur_cost < cost[(c2,B,v1,v2)] and\
                        self.__loc_rat_capable(infra, ns, v2, c2):
                    cost[(c2,B,v1,v2)] = incur_cost
                    prev[(c2,B,v1,v2)] = (c1,A)
                    needed_cpu[(c2,B,v1,v2)] = need_cpu

                    if hop + 1 < len(vls): # refresh CPU status for next iters
                        for c,B_ in filter(lambda C: C[0]==c2,
                                           self.__aux_g.nodes()):
                            _,v3,__ = vls[hop+1]
                            curr_cpu[(c,B_,v2,v3)] =\
                                    curr_cpu[(c2,B,v1,v2)] - need_cpu

            # Check if delay relax is needed
            no_mapping = False
            if all(map(lambda C: cost[(C[0],C[1],v1,v2)] == float('inf'),
                       self.__aux_g.nodes())):
                self.__log.info('relax restriction for virtual link  (' +\
                                str(v1) + ',' + str(v2) + ')')
                no_mapping = True
                possible_ds = []
                for ((c1,A),(c2,B)) in self.__aux_g.edges():
                    if curr_cpu[(c2,B,v1,v2)] > 0:
                        possible_d = ns.nodes[v2]['lv'] / (1 -
                                     FPTASMapper.DELAY_FACTOR * vl_d['bw'] /\
                                     curr_cpu[(c2,B,v1,v2)]) +\
                                     self.__aux_g[(c1,A)][(c2,B)]['delay']
                        if possible_d > hop_delay[hop] - l_d['delay']:
                            possible_ds += [possible_d]

                possible_ds = list(set(possible_ds))
                possible_ds.sort()

                hop_delay[hop] = possible_ds[relax+relaxed]
                self.__log.info('new delay=' + str(hop_delay[hop]))
                relaxed += 1
            else:
                hop += 1
                if relaxed > 1 and hop < len(hop_delay) - 2:
                    hop_delay[hop+1:] = [hd - (possible_ds[relax] -\
                                            hop_delay[hop]) /
                                            len(hop_delay[hop+1:])\
                                         for hd in hop_delay[hop+1:]]


        # Get the best solution
        self.__log.info('looking for best candidates')
        candidates = [(c,A) for (c,A) in self.__aux_g.nodes\
                      if cost[(c,A,vls[-1][0],vls[-1][1])] != float('inf')]
        min_cost, c_f, A_f = float('inf'), None, None
        for c,A in candidates:
            if cost[(c,A,vls[-1][0],vls[-1][1])] < min_cost:
                c_f, A_f = c, A

        return self.__get_mapping(c_f, A_f, prev, needed_cpu, vls)


    @staticmethod
    def map_reliability(infra: nx.classes.digraph.DiGraph,
                        mapping: dict) -> float:
        """Retrieve the reliability of a ns mapping

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :path: dict: mapping decissions dictionary
        :returns: the reliability

        """
        reliab = 1

        # Multiply by hosts reliability
        for vnf in [k for k in mapping.keys()\
                    if k != 'worked' and type(k) != tuple]:
            reliab *= infra.nodes[mapping[vnf]['host']]['reliability']

        # Multiply by links' reliability
        for vl in [k for k in mapping.keys()\
                   if k != 'worked' and type(k) == tuple]:
            limits = [mapping[vl][0], mapping[vl][-1]]
            for h1,h2 in zip(mapping[vl][:-1], mapping[vl][1:]):
                if h1 not in limits:
                    reliab *= infra.nodes[h1]['reliability']
                if h2 not in limits:
                    reliab *= infra.nodes[h2]['reliability']

                reliab *= infra[h1][h2]['reliability']

        return reliab


    @staticmethod
    def map_cost(infra: nx.classes.digraph.DiGraph,
                 ns: nx.classes.digraph.DiGraph, mapping: dict) -> float:
        """Retrieves the cost of a given mapping

        :infra: nx.classes.digraph.DiGraph: infrastructure digraph instance
        :ns: nx.classes.digraph.DiGraph: network service graph
        :mapping: dict: dictionary with the result of map() method
        :returns: cost of the given mapping

        """
        cost = 0

        # VNF mapping cost
        for vnf in [k for k in mapping.keys() if type(k) != tuple and\
                                                 k != 'worked']:
            for r in infra.nodes[mapping[vnf]['host']]['cost'].keys():
                cost += infra.nodes[mapping[vnf]['host']]['cost'][r] *\
                            mapping[vnf]['cpu']

        # VL mapping cost
        for vl in [k for k in mapping.keys() if type(k) == tuple]:
            for h1,h2 in zip(mapping[vl], mapping[vl][1:]):
                cost += infra[h1][h2]['cost'] * ns[vl[0]][vl[1]]['bw']

        return cost


    @staticmethod
    def map_delay(infra: nx.classes.digraph.DiGraph,
                  ns: nx.classes.digraph.DiGraph, mapping: dict) -> float:
        """Retrieve the delay of the mapped network service

        :infra: nx.classes.digraph.DiGraph: infrastructure digraph instance
        :ns: nx.classes.digraph.DiGraph: network service graph
        :mapping: dict: dictionary with the result of map() method
        :returns: delay of the given mapping

        """
        delay = 0
        vls = FPTASMapper.ordered_vls(ns)
        
        # Propagation delay
        for vl in [k for k in mapping.keys() if type(k) == tuple]:
            # Propagation delay
            for h1,h2 in zip(mapping[vl], mapping[vl][1:]):
                delay += infra[h1][h2]['delay']

            # Processing delay
            if not re.match('^e\d+$', vl[1]):
                assigned_cpu = mapping[vl[1]]['cpu']
                pr_del = ns.nodes[vl[1]]['lv'] /\
                         (1 - FPTASMapper.DELAY_FACTOR *
                                 ns[vl[0]][vl[1]]['bw']/ assigned_cpu)
                delay += pr_del

        return delay

