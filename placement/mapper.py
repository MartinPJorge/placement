from abc import ABCMeta, abstractmethod
from haversine import haversine
import copy
import networkx as nx
import sys
import os
import re
import logging
from itertools import islice, chain, combinations
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from checker import AbstractChecker, CheckFogDigraphs, CheckBasicGraphs
from functools import reduce
from utils import k_shortest_paths, k_reasonable_paths
from math import log, sqrt



def eucl_dis(a, b):
    """Computes the euclidean distance of two points

    :a: tuple|list with (x,y) coordinates
    :b: tuple|list with (x,y) coordinates
    :returns: euclidean distance between a and b

    """
    return sqrt(reduce(lambda d1,d2: d1+d2,[(a_-b_)**2 for a_,b_ in zip(a,b)]))





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
            if self.__metric == 'euclidean':
                hosts = filter(lambda h: 'location' in infra.nodes[h]\
                        and eucl_dis(infra.nodes[h]['location'], vloc) <= vrad,
                        hosts)
            else:
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
            if self.__metric == 'euclidean':
                hosts = filter(lambda h: 'location' in infra.nodes[h]\
                        and eucl_dis(infra.nodes[h]['location'], vloc) <= vrad,
                        hosts)
            else:
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


    def __init__(self, checker: CheckFogDigraphs, metric: str = 'wgs84',
                 log_out: str = 'aux_g.loh'):
        """Inits the mapper with its associated graphs checker

        :checker: CheckFogDigraph: instance of a fog graph checker
        :metric: str: 'wgs84' or 'euclidean' distance
        :log_out: str: file to output the log of the mapper
        :returns: None

        """
        self.__checker = checker
        self.__log = logging.getLogger(name=log_out)
        file_handler = logging.FileHandler(log_out, mode='w')
        self.__log.addHandler(file_handler)
        self.__metric = metric if metric == 'euclidean' else 'wgs84'


    def get_metric(self) -> str:
        """

        :returns: str: the internal metric

        """
        return self.__metric


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
                                ('endpoint' in infra.nodes[n] and\
                                infra.nodes[n]['endpoint'])])
        self.__log.info('comp_nodes=%s' % comp_nodes)

        if src not in comp_nodes:
            comp_nodes.union(src)
        src_paths = {}

        # Find all paths between computational nodes
        self.__log.info('finding all paths between nodes')
        for from_ in comp_nodes:
            src_paths[from_] = {}
            #for to_ in [c for c in comp_nodes if c != from_]:
            for to_ in comp_nodes:
                # Create the self-link
                if from_ == to_:
                    src_paths[from_][to_] = {
                        'paths': [from_, to_],
                        'delays': [0],
                        'reliability': [1],
                        'bw': [sys.maxsize],
                        'cost': [0]
                    }
                    continue

                if not nx.has_path(infra, from_, to_):
                    print('no path')
                    continue
                else:
                    print('there is a path')
                #for path in k_shortest_paths(infra, from_, to_,
                #                             k=k, weight='delay'):
                for path in k_reasonable_paths(infra, from_, to_,
                        k, 'delay'):
                    print('\t' % path)
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

        print('these are the paths')
        import json
        print(json.dumps(src_paths, indent=2))

        # for dst in src_paths[src]:
        #     if 'Azure' in dst:
        #         print('from {} to {} = {}'.format(src,dst,src_paths[src][dst]))

        # Build the auxiliary graph
        self.__log.info('inserting (c,A) nodes in the auxiliary graph')
        self.__aux_g = nx.DiGraph()
        for comp_node in comp_nodes:
            for tau_ in range(tau + 1):
                self.__aux_g.add_node((comp_node,tau_),
                                      **infra.nodes[comp_node])

        # for c2 in src_paths['e1']:
        #     print('from {} to {}:'.format('e1',c2))
        #     for i in range(len(src_paths['e1'][c2]['paths'])):
        #         w1 = -1 * tau * log(1 /\
        #                 (src_paths['e1'][c2]['reliability'][i]*\
        #                     infra.nodes[c2]['reliability'])) /\
        #                         log(ereliab)
        #         print('  path={}'.format(src_paths['e1'][c2]['paths'][i]))
        #         print('    w1={}'.format(w1))
        #         print('    reliab={}'.format(src_paths['e1'][c2]['reliability'][i]))
        #         print('    delay={}'.format(src_paths['e1'][c2]['delays'][i]))

        # Connect the auxiliary graph nodes
        self.__log.info('connect nodes (c,A)--(c2,B) of auxiliary nodes')
        for (c1,A) in self.__aux_g.nodes():
            for (c2,B) in self.__aux_g.nodes():

                # self-loop
                if c1 == c2: 
                    self.__aux_g.add_edge((c1,A), (c2,B), w1=0,
                                delay=0, path=[c1,c2],
                                bw=sys.maxsize, cost=0)
                    continue

                print('\ttrying to connect %s--%s' %\
                        ((c1,A), (c2,B)) )
                if not nx.has_path(infra, c1, c2):
                    print('\t\tno path')
                    continue

                # GET PATH WITH LOWEST DELAY SATISFYING A+W1<=B
                delay, w1, idx = float('inf'), float('inf'), 0
                for i in range(len(src_paths[c1][c2]['paths'])):
                    curr_w1 = -1 * tau * log(1 /\
                                 (src_paths[c1][c2]['reliability'][i]*\
                                     infra.nodes[c2]['reliability'])) /\
                                         log(ereliab)
                    curr_delay = src_paths[c1][c2]['delays'][i]
                    if curr_delay < delay and A+curr_w1<=B:
                        delay, w1, idx = curr_delay, curr_w1, i
                    
                # RETRIEVE PATH WITH MAXIMUM RELIABILITY
                # idx = src_paths[c1][c2]['reliability'].index(\
                #         max(src_paths[c1][c2]['reliability']))
                # w1 = -1 * tau * log(1 /\
                #         (src_paths[c1][c2]['reliability'][idx]*\
                #             infra.nodes[c2]['reliability'])) /\
                #                 log(ereliab)

                # if c1 == 'e1' and A + w1 <= B:
                #     print('link {} -- {}'.format((c1,A), (c2,B)))
                #     for i in range(len(src_paths[c1][c2]['reliability'])):
                #         print('  idx={}'.format(i))
                #         print('  path={}, reliab={}, delay={}'.format(
                #             src_paths[c1][c2]['paths'][idx],
                #             src_paths[c1][c2]['reliability'][idx],
                #             src_paths[c1][c2]['delays'][idx]))

                if A + w1 <= B:
                    self.__aux_g.add_edge((c1,A), (c2,B), w1=w1,
                                delay=src_paths[c1][c2]['delays'][idx],
                                path=src_paths[c1][c2]['paths'][idx],
                                bw=src_paths[c1][c2]['bw'][idx],
                                cost=src_paths[c1][c2]['cost'][idx])


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
                distance = eucl_dis(vnf_coords, host_coords)\
                        if self.__metric == 'euclidean' else\
                        haversine(vnf_coords, host_coords)
                if distance > ns.nodes[vnf]['location']['radius']:
                    self.__log.info('\tdistance to %s: %f' % (host, distance))
                    self.__log.info("\trequired one: %f" % ns.nodes[vnf]['location']['radius'])

                    return False

        # Check RAT constraints
        if 'rats' in ns.nodes[vnf] and ns.nodes[vnf]['rats'] != None:
            # if vnf == 'AP' and host in ['femto', 'pico_down', 'pico_top', 'micro']:
            #     print('VNF.rats={}  host.rats={}'.format(ns.nodes[vnf]['rats'], infra.nodes[host]['rats']))
            if 'rats' not in infra.nodes[host] or\
                    infra.nodes[host]['rats'] == None:
                return False
            elif not all(map(lambda v_rat: v_rat in infra.nodes[host]['rats'],
                             ns.nodes[vnf]['rats'])):
                return False

        return True 


    def __remaining_cpu(self, vls: list, hop: int, curr_cpu: dict, prev: dict,
                        needed_cpu: dict, asked_node, src_node, src_tau: int,
                        infra: nx.classes.digraph.DiGraph) -> bool:
        """Calculates the remaining CPU inside asked_node during the mapping

        :vls: list: [(vnf1, vnf2, {...}), ...]
        :hop: int: index of the asked hop
        :curr_cpu: dict: of current CPU at each stage of the mapping
        :prev: dict: dictionary of the previous infra nodes in the mapping
        :needed_cpu: dict: dictionary of the needed CPU of mapping decisions
        :asked_node: id of the node in the auxiliary graph
        :src_node: node where last VNF was mapped
        :src_tau: int: tau of the departing node
        :infra: nx.classes.digraph.DiGraph: infrastructure graph of the mapping
        :returns: bool

        """
        remain_cpu = infra.nodes[asked_node]['cpu']
        curr_hop = hop - 1
        curr_c = src_node
        curr_tau = src_tau

        while curr_hop >= 0:
            v1,v2,_ = vls[curr_hop]
            if curr_c == asked_node:
                remain_cpu -= needed_cpu[(curr_c,curr_tau,v1,v2)]
            if curr_hop > 0:
                prev_pair = prev[(curr_c,curr_tau,v1,v2)]
                if prev_pair != None:
                    curr_c, curr_tau = prev_pair
                else:
                    curr_hop = 0
            curr_hop -= 1

        return remain_cpu


    def __prune_excess(self, vls: list, prev: dict, needed_cpu: dict,
                       cost: dict, infra: nx.classes.digraph.DiGraph):
        """Set to inf the cost of those solutions that excess CPU resources

        :vls: list: [(vnf1, vnf2, {...}), ...]
        :prev: dict: dictionary of the previous infra nodes in the mapping
        :needed_cpu: dict: dictionary of the needed CPU of mapping decisions
        :cost: dict: dictionary of mappings' costs
        :infra: nx.classes.digraph.DiGraph: infrastructure graph of the mapping
        :returns: Nothing

        """
        # Feasible solutions
        candidates = [(c,A) for (c,A) in self.__aux_g.nodes\
                      if cost[(c,A,vls[-1][0],vls[-1][1])] != float('inf')]

        for c,A in candidates:
            consumed_cpu = {}
            hop = -1
            curr_c = c
            curr_A = A

            # Store CPU consumed by each VNF
            while hop >= -1*len(vls):
                v1,v2,_ = vls[hop]
                if curr_c not in consumed_cpu:
                    consumed_cpu[curr_c] = 0
                
                consumed_cpu[curr_c] += needed_cpu[(curr_c,curr_A,v1,v2)]

                curr_c, curr_A = prev[(curr_c,curr_A,v1,v2)]
                hop -= 1

            for c_ in consumed_cpu:
                print('({},{})[{}]={}'.format(c,A,c_,consumed_cpu[c_]))

            # Check if CPU resources is exceeded at some infra node
            for c_ in consumed_cpu:
                if infra.nodes[c_]['cpu'] < consumed_cpu[c_]:
                    print('{} CPUs in {}, but {} consumed'.format(
                        infra.nodes[c_]['cpu'], c_,consumed_cpu[c_]))
                    cost[(c,A,vls[-1][0],vls[-1][1])] = float('inf')
                    break
            print('::')
                

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
        if not self.__checker.check_infra(infra=infra) or\
                not self.__checker.check_ns(ns=ns, check_vcore_Mb=True):
            return { 'worked': False }

        endpoint = list(filter(lambda vnf: ns.in_degree(vnf) == 0,
                               ns.nodes()))[0]
        self.__log.info('endpoint=%s' % endpoint)
        self.__log.info('required reliab %f' % ns.nodes[endpoint]["reliability"])
        self.__build_aux(infra=infra, src=endpoint, k=k, tau=tau,
                         ereliab=ns.nodes[endpoint]['reliability'])
        self.__log.info('setting auxiliary variables')
        vls = FPTASMapper.ordered_vls(ns)
        hop_delay = [ns.nodes[endpoint]['delay']/len(ns.edges)] * len(ns.edges)
        print('FPTAS: end_delay={}'.format(ns.nodes[endpoint]['delay']))

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

            for a in self.__aux_g.edges(data=True):
                self.__log.info(a)
            to_visit = self.__aux_g.edges(data=True) if not first_vl else\
                       filter(lambda e: e[0][0] == endpoint and e[0][1] == 0,
                              self.__aux_g.edges(data=True))
            to_visit = list(to_visit)
            self.__log.info('to_visit=%s' % to_visit)

            # for ((c1,A),(c2,B),l_d) in to_visit:
            #     if 'ower' in c2 or 'enter' in c2:
            #         print('\tto visit {}'.format((c2,B)))
            #         print('\tdelay={}'.format(l_d['delay']))
            #         print('\t{}'.format(l_d['path']))

            # print('\t\tmapping: {}[\'bw\']={}'.format((v1,v2),vl_d['bw']))
            # print('imposing hop delay={}'.format(hop_delay[hop]))
            # print('there are {} candidates'.format(list(set(map(lambda v: v[1][0],
            #     to_visit)))))
            for ((c1,A),(c2,B),l_d) in filter(lambda e:\
                                            e[2]['bw'] >= vl_d['bw'], to_visit):
                # if any(map(lambda h: infra.nodes[h]['type'] == 'pico_cell',
                #             self.__aux_g[(c1,A)][(c2,B)]['path'])) or\
                #         'Azure' in c2:
                # print('\t\t==>==>lv={},hop_{}_delay={},(c2,B)={},LL_delay={}'.format(
                #     ns.nodes[v2]['lv'], hop, hop_delay[hop], (c2,B), l_d['delay']))
                # print('\t\tpath={}'.format(self.__aux_g[(c1,A)][(c2,B)]['path']))
                # DEPRECATED WRONG WAY TO OBTAIN IT
                # need_cpu = FPTASMapper.DELAY_FACTOR * vl_d['bw'] /\
                #            (1 - ns.nodes[v2]['lv'] /\
                #                    (hop_delay[hop] - l_d['delay'])) if\
                #              l_d['delay'] < hop_delay[hop] else float('inf')

                self.__log.info('%s-%s' % ((c1,A),(c2,B)) )
                # use the PS approach
                need_cpu = (1 / (hop_delay[hop] - l_d['delay']) +\
                        ns[v1][v2]['bw']*1e-3) * ns.nodes[v2]['vcore_per_Mb']\
                        if l_d['delay'] < hop_delay[hop] else float('inf')
                #print('\t\twe\'ll need {} cpus'.format(need_cpu))
                self.__log.info('\t%s--%s requires %f CPUs' %\
                        ((c1,A),(c2,B), need_cpu) )
                self.__log.info('\thop delay={}, LL_delay = {}'.format(
                    hop_delay[hop], l_d['delay']))

                incur_cost = infra.nodes[c2]['cost']['cpu'] * need_cpu +\
                             self.__aux_g[(c1,A)][(c2,B)]['cost'] *vl_d['bw']+\
                             (0 if first_vl else cost[(c1,A,v0,v1)])

                # Obtain remaining CPU ar c2 along the taken path
                remaining_cpu = self.__remaining_cpu(vls, hop, curr_cpu, prev,
                                                     needed_cpu, c2, c1, A,
                                                     infra)
                # print('\t\trequires {}CPUs for vnf={} in host={}'.format(need_cpu, v2, c2))
                # print('\t\t  remains={}'.format(remaining_cpu))
                # if v2 == 'AP' and c2 in ['femto', 'pico_down', 'pico_top', 'micro']:
                #     loc_cap = self.__loc_rat_capable(infra, ns, v2, c2)
                #     print('\n\t{} is {} loc_rat_capable for vnf {}'.format(c2,
                #         loc_cap, v2))
                #     print('\tneeded_cpu={}, remaining={}'.format(need_cpu,
                #         remaining_cpu))
                #     print('\tincured_cost={} -- current cost={}'.format(incur_cost,cost[(c2,B,v1,v2)]))
                #     print('(c1,A)=({},{})  (c2,B)=({},{})  (v0,v1)=({},{})'.format(
                #                 c1,A,c2,B,v0,v1))
                #     print('cost[(c1,A,v0,v1)]={}'.format(cost[(c1,A,v0,v1)]))

                self.__log.info('\t__loc_rat_capable=%s' % self.__loc_rat_capable(infra, ns,v2, c2))

                if remaining_cpu >= need_cpu and\
                        incur_cost < cost[(c2,B,v1,v2)] and\
                        self.__loc_rat_capable(infra, ns, v2, c2):
                    cost[(c2,B,v1,v2)] = incur_cost
                    prev[(c2,B,v1,v2)] = (c1,A)
                    needed_cpu[(c2,B,v1,v2)] = need_cpu
                    
                    # Consume its current CPU
                    # curr_cpu[(c2,B,v1,v2)] = remaining_cpu - need_cpu
                    # print('\thost {} can have vnf {}'.format(c2,v2))


                    if hop + 1 < len(vls): # refresh CPU status for next iters
                        _,v3,__ = vls[hop+1]
                        for c,B_ in filter(lambda C: C[0]==c2,
                                           self.__aux_g.nodes()):
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
                for ((c1,A),(c2,B),l_d) in self.__aux_g.edges(data=True):
                    if curr_cpu[(c2,B,v1,v2)] > 0:
                        # DEPRECATED WRONG FORMULA
                        # possible_d = ns.nodes[v2]['lv'] / (1 -
                        #              FPTASMapper.DELAY_FACTOR * vl_d['bw'] /\
                        #              curr_cpu[(c2,B,v1,v2)]) +\
                        #              self.__aux_g[(c1,A)][(c2,B)]['delay']

                        # use this one for large scenario
                        possible_d = 1/ (curr_cpu[(c2,B,v1,v2)]*20 -\
                                ns[v1][v2]['bw']*1e-3) +\
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

        # Prune non-feasible solutions
        #self.__prune_excess(vls, prev, needed_cpu, cost, infra)

        # Get the best solution
        self.__log.info('looking for best candidates')
        candidates = [(c,A) for (c,A) in self.__aux_g.nodes\
                      if cost[(c,A,vls[-1][0],vls[-1][1])] != float('inf')]
        min_cost, c_f, A_f = float('inf'), None, None
        for c,A in candidates:
            self.__log.info('candidate %s has cost %f' %\
                            ((c,A), cost[(c,A,vls[-1][0],vls[-1][1])]) )
            if cost[(c,A,vls[-1][0],vls[-1][1])] < min_cost:
                c_f, A_f = c, A
                min_cost = cost[(c,A,vls[-1][0],vls[-1][1])]

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
                vnf_r_cost = infra.nodes[mapping[vnf]['host']]['cost'][r] *\
                            mapping[vnf]['cpu']
                mapping[vnf]['cost'] = vnf_r_cost
                cost += vnf_r_cost
        cpu_cost = cost

        # VL mapping cost
        for vl in [k for k in mapping.keys() if type(k) == tuple]:
            for h1,h2 in zip(mapping[vl], mapping[vl][1:]):
                cost += infra[h1][h2]['cost'] * ns[vl[0]][vl[1]]['bw']
        print('\t\t  ==CPU cost={}, BW cost={}'.format(cpu_cost,
            cost - cpu_cost))
        mapping['link_cost'] = cost - cpu_cost

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
                # DEPRECATED AND WRONG PROCESSING DELAY
                # pr_del = ns.nodes[vl[1]]['lv'] /\
                #          (1 - FPTASMapper.DELAY_FACTOR *
                #                  ns[vl[0]][vl[1]]['bw']/ assigned_cpu)

                # use this one for large scenario
                lamb = ns[vl[0]][vl[1]]['bw']
                pr_del = 1 / (assigned_cpu*20 - lamb*1e-3)

                delay += pr_del

        return delay


class FMCMapper(AbstractMapper):

    """Class definition of the Follow Me Chain (FMC) algorithm [fmc].
    This version corrects [fmc] pitfall of not mapping all virtual
    links ([fmc] visits the graph using a node-based BFS), and uses
    k-shortest_paths rather than the range-based DFS, which does not
    scale.

    [fmc] Chen, Yan-Ting, and Wanjiun Liao. "Mobility-aware service function
    chaining in 5g wireless networks with mobile edge computing." ICC 2019-2019
    IEEE International Conference on Communications (ICC). IEEE, 2019.
    """


    def __init__(self, checker: CheckBasicGraphs):
        """Initializes the FMC mapper.

        :checker: CheckBasicGraphs: instance of a fog graph checker

        """
        self.__checker = checker

        # TODO - remove
        ### self.__Ms = None

        ### if not self.__checker.check_infra(infra):
        ###     raise ValueError(f'infra does not pass the check')

        ### # Create a full meshed graph with servers M as vertices
        ### # each edge (Mi, Mj) has an associated path
        ### self.__Ms = nx.Graph()
        ### self.__Ms.add_nodes_from({
        ###     M: {'cpu': infra[M]['cpu']}
        ###     for M in filter(lambda n:
        ###             any(lambda s: s in infra[n]['name'], Mnames),
        ###         infra.nodes)
        ### })
        ### # Find shortest paths among servers and use them as (Mi,Mj)
        ### self.__Ms.add_edges_from({
        ###     (M1,M2): {'path':
        ###         infra.shortest_path(source=M1, target=M2, weight='delay')}
        ###     for (M1,M2) in combinations(seld.__Ms.nodes, 2)
        ### })
        


    # TODO - UNUSED
    def __consume_bw(self, infra: nx.classes.graph.Graph,
            n1: int, n2: int, bw: float, path: list=None) -> int:
        """
        Consume the specified bandwidth bw along the path connecting
        nodes n1 and n2 in the infra graph

        :infra: nx.classes.graph.Graph: infrastructure graph
        :n1: int: first graph node
        :n2: int: first graph node
        :bw: float: bandwidth to be consumed
        :path: list: (optional) if not specified, n1 and n2 must be present
                     in the self.__Ms graph
        :returns: int: 0 - success
                       1 - not enough bandwidth
                       2 - missing path

        """
    
        if not path and (n1 not in self.__Ms.nodes or\
                n2 not in self.__Ms.nodes):
            return 2

        if not path:
            path = zip(self.__Ms[n1,n2]['path'][1:],
                    self.__Ms[n1,n2]['path'][:-1])
        if bw > min(map(lambda a,b: infra[a,b]['bandwidth'], path)):
            return 1
        for a,b in path:
            infra[a,b]['bandwidth'] -= bw
            


    # TODO - remove the adjacency parameter and refactor code
    def map(self, infra: nx.classes.graph.Graph,
            ns: nx.classes.graph.Graph, adj: int,
            tr: int, ts: int) -> dict:
        """Maps a network service on top of an infrastructure.

        :infra: nx.classes.graph.Graph: infrastructure graph
        :ns: nx.classes.graph.Graph: network service graph
        :adj: int: graph depth of "adjacent servers"
        :tr: int: residence time of user in cell
        :ts: int: user service time
        :returns: dict: mapping decissions dictionary

        :Note: the mapping assumes the first vnf in the ns corresponds
        to an endpoint within the fog

        :Note: the mapping contains ids of both infra, and ns graph

        """
        mapping = {
            'worked': True
        }
        for n in ns.nodes:
            mapping[n] = list(filter(lambda n: infra.nodes[n]['cpu'] >= 0 and\
                    ('edge' in infra.nodes[n]['name'] or\
                        'fog' in infra.nodes[n]['name']), infra.nodes))[0]
        for n1,n2 in ns.edges():
            mapping[n1,n2] = []
        ## How a mapping looks like
        # mapping = {
        #     "worked": true,
        #     "AP_selection": {
        #         "1": "23"  # name_23="cell4",
        #            [...]
        #         "24": "52" # name_52="cell33"
        #     },
        #     "Objective_value": 293.89509,
        #     "Running_time": 0.013942956924438477,
        #     "1": "1"       # "nf0": "endpoint_sq1"
        # }

        # Check that graphs have correct format
        if not self.__checker.check_infra(infra) or\
                not self.__checker.check_ns(ns):
            mapping['worked'] = False
            return mapping

        # Initialize queue q, enqueue the first VNF
        # (closest to user) in SFC to q
        # q contains VNF indexes in the networkx graph
        n0_ = list(ns.nodes)[0]
        q = [n0_]

        # Initialize D as empty set
        D = set()

        # M -> set of nodes with computational capabilities
        #      that are edge/fog
        M = list(filter(lambda n: 'edge' in infra.nodes[n]['name']\
                            or 'fogNode' in infra.nodes[n]['name']\
                            or 'endpoint' in infra.nodes[n]['name'],
                        infra.nodes))

        # Map first VNF to the endpoint specified in its location constraint
        # in case it doesnt have it, map wherever it can
        if 'location_constraint' in ns.nodes[n0_]:
            mapping[n0_] = ns.nodes[n0_]['location_constraints'][0]
            Mi = mapping[n0_]
        else:
            Mi = list(filter(lambda m:
                    infra.nodes[m]['cpu'] >= ns.nodes[n0_]['cpu'], M))[0]
            mapping[n0_] = Mi



        # Mapping loop
        while len(q) > 0:
            n = q.pop(0)
            print(f'mapping VNF={n}')
            print(f'Mi={Mi}')

            # virtual link l connected to n do
            # n0 <- the other endpoint of l;
            #  if n0 has not been embedded then
            for n0 in filter(lambda n0: n0 not in mapping
                    or ((n,n0) not in mapping) and ((n0,n) not in mapping),
                        ns[n].keys()):  
                l = ns[n][n0]

                print(f'vl={(n,n0)}')

                # Find shortest paths from current compute node Mi to Mj
                Mi_to = {
                    m: nx.shortest_path(infra, source=Mi, target=m,
                        weight='delay')
                    for m in filter(lambda Mj: Mj != Mi, M)
                }
                ### Obtain the "adjacent" MEC servers adj=5 -> access ring
                adjM = list(filter(lambda Mi: len(Mi_to[Mi]) <= adj,
                                   Mi_to.keys()))

                # Filter by possible location constraints
                if 'location_constraints' in ns.nodes[n0]:
                    adjM = filter(lambda m:\
                            m in ns.nodes[n0]['location_constraints'],
                            adjM)

                # C <- {Mj |adjacent MEC nodes of Mi & Mi} \ D;
                C = set(adjM).difference(D)

                # C = emptyset -> return error in mapping
                if len(C) == 0:
                    mapping['worked'] = False
                    return mapping

                # calculate the inner product for all Mj in C
                # (rci (t), rbij (t)) · (1, w)
                inner_product = {}
                for Mj in C:
                    rci = infra.nodes[Mj]['cpu']
                    rbij = min(map(lambda e: infra[e[0]][e[1]]['bandwidth'],
                                zip(Mi_to[Mj][:-1], Mi_to[Mj][1:])))
                    w = ts / tr
                    inner_product[Mj] = [rci*1, rbij*w]

                # If n0 was previously mapped, use that server
                print(f'n0={n0} not in mapping={n0 not in mapping}')
                Mj = max(inner_product) if n0 not in mapping else mapping[n0]

                # embed n0 onto the Mj with max inner product
                mapping[n0] = Mj 
                infra.nodes[Mj]['cpu'] -= ns.nodes[n0]['cpu']

                # embed l onto the eij
                if Mi != Mj:
                    embed_path = Mi_to[Mj]
                    for A,B in zip(embed_path[1:], embed_path[:-1]):
                        infra[A][B]['bandwidth'] -= l['bandwidth']
                    mapping[n,n0] = embed_path

                #  enqueue n0 to q, mark n0 as embedded;
                q.append(n0)

                if Mj != Mi:
                    D = D.union({Mj})
                    Mi = Mj

        return mapping


    def __servers_graph(self,
            infra: nx.classes.graph.Graph) -> nx.Graph:
        """Creates a full-meshed servers' graph, with edges
        representing the shortest path among them.

        infra: nx.classes.graph.Graph: infrastructure graph

        return: nx.Graph: full-meshed servers' graph
        """

        # Create a full meshed graph with servers M as vertices
        # each edge (Mi, Mj) has an associated path
        Ms = nx.Graph()
        Ms.add_nodes_from({
            M: {'cpu': infra.nodes[M]['cpu']}
            for M in filter(lambda n:
                    any(map(lambda _fix: _fix in infra.nodes[n]['name'],
                        ['edge', 'fog', 'endpoint'])),
                    infra.nodes)
        })
        # Find shortest paths among servers and use them as (Mi,Mj)
        Ms.add_edges_from((
            (M1, M2, {'path':
                nx.shortest_path(infra, source=M1, target=M2, weight='delay')})
            for (M1,M2) in combinations(Ms.nodes, 2)
        ))
        for (M1,M2) in combinations(Ms.nodes, 2):
            i, delay, bw = 0, 0, float('inf')
            while i < len(Ms[M1][M2]['path']) - 1:
                n1, n2 = Ms[M1][M2]['path'][i], Ms[M1][M2]['path'][i+1]
                delay += infra[n1][n2]['delay']
                bw = min(bw, infra[n1][n2]['bandwidth'])
                i += 1
            nx.set_edge_attributes(Ms,
                    {(M1,M2): {'delay': delay, 'bandwidth': bw}})

        # Add self-loops to enhance mapping in same VNF
        Ms.add_edges_from((
            (M1, M1, {'path': [M1,M1], 'delay': 0, 'bandwidth': float('inf')})
            for M1 in Ms.nodes
        ))

        return Ms





    def handover(self, infra: nx.classes.graph.Graph,
            ns: nx.classes.graph.Graph, prev_mapping: dict,
            tr: int, ts: int, Sl: float, paths: int=None) -> dict:
        """Performs the VNF and VL migrations due to a cell handover

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :adj: int: graph depth of "adjacent servers"
        :prev_mapping: dict: previous mapping
        :tr: int: residence time of user in cell
        :ts: int: user service time
        :Sl: float: end-to-end service delay requirement
        :paths: int: the number of paths computed for each (src,dst)
        :returns: dict: mapping decissions dictionary
                  None: no cell used in prev_mapping, no handover
                        required

        :Note: ns must match the provided in the previous map() 

        :Note: the mapping contains ids of both infra, and ns graph

        """

        if paths == None:
            paths = len(ns.nodes)
        print(f'I receive delay Sl={Sl}')

        mapping = dict(prev_mapping)

        edge_or_cloud = any(map(lambda n: infra.nodes[n]['type'] == 'server',
                infra.nodes))

        # Detect the vl traveling over a cell link
        vl_over_cell = []
        if edge_or_cloud:
            mapped_vls = filter(lambda k: type(k) == tuple,
                    prev_mapping.keys())
            vl_paths = map(lambda vl: prev_mapping[vl], mapped_vls)
            vls_over_cell = list(filter(lambda vl:
                        any(map(lambda n: infra.nodes[n]['type'] == 'cell',
                            prev_mapping[vl])),
                    mapped_vls))

        # Check if no cell is used in prev_mapping
        if vls_over_cell == []:
            return None
        else:
            vl_over_cell = vls_over_cell[0]

        # p0 - original path of the previous mapping (just servers)
        #      [M1,M2,...,Mn,Mn+1]
        p0 = list(map(lambda v: prev_mapping[v],
                filter(lambda k: type(k) not in (tuple,str), prev_mapping)))


        #print(f'vl_over_cell={vl_over_cell}')
        cell_new = list(filter(lambda n: infra.nodes[n]['type'] == 'cell',
            prev_mapping[vl_over_cell]))[0]
        #print(f'cell_new={cell_new}')
        #print(f' data={infra.nodes[cell_new]}')
        Mold = prev_mapping[vl_over_cell][-1]

        
        # Full-meshed servers' graph (and endpoint)
        Ms = self.__servers_graph(infra)
        #print(f'servers graph nodes={Ms.nodes}')


        # {pi} ← {all paths that is origined from
        #         Mold to Mnew & path delay < Sl requirement};
        src = prev_mapping[0] # 0 is the first VNF in NS
        #print(f'looking for paths from src={src}')
        p = []
        # print(f'Ms has {len(Ms.node)}-nodes and {len(Ms.edges)} edges')
        p = [k_shortest_paths(G=Ms, source=src, target=t, k=paths,
                weight='delay') for t in set(Ms.nodes).difference({src})]
        p = list(chain(*p)) # unpack the lists of paths
        #print(f'before filtering p={p}')
        #print(f'before filtering p[0]={p[0]}')
        p = list(filter(lambda pi:
                Ms[pi[0]][pi[1]]['delay'] <= Sl if len(pi) == 2 else\
                sum(map(lambda Mlnk: Ms.edges[Mlnk]['delay'],
                    zip(pi[:-1], pi[1:]))) <= Sl,
                p))

        # Calculate J value for all paths in {pi };
        J = lambda pi: len(set(p0).intersection(set(pi))) /\
                len(set(p0).union(set(pi)))
        # Sort out {pi} in an decreasing order of J;
        p.sort(reverse=True, key=J)

        #print(f'prev p0 = {list(p0)}')
        #print(f'sorted p: {p}')


        ##################
        # Migration loop #
        ##################
        stop, success = False, False
        i = 1
        q = []
        print(f'len(p)={len(p)}')
        while (not stop) and (i < len(p)):
            n1st = list(ns.nodes)[0]
            q.insert(0, n1st)
            success = True
            mapping['migrated'], mapping['remain'], migrations = [], [], {}

            while len(q) > 0:
                n = q.pop()

                # print(f'\tchecking path p[{i}]={p[i]} for vnf={n}')
                if prev_mapping[n] in p[i]:
                    mapping['remain'].append(n)
                # if (n not satisfies requirement) or (n not allocated on pi)
                #     cpu requirements are ensured in previous mapping
                elif prev_mapping[n] not in p[i]:
                    # print(f'\t vnf={n} was on {prev_mapping[n]}',
                    #         f'and that is not inside p[{i}]')

                    # max_n' {bw(n,n')}
                    max_vl_bw = ns[n][reduce(lambda n2,n2_:
                            n2 if ns[n][n2]['bandwidth'] > ns[n][n2_]['bandwidth'] else n2_,
                        ns.neighbors(n))]['bandwidth']

                    # enough over the migration link
                    Mis = filter(lambda M:
                            Ms[prev_mapping[n]][M]['bandwidth'] >= max_vl_bw\
                                and M in p[i],
                        Ms.neighbors(prev_mapping[n]))

                    # Only compute nodes with enough CPU
                    Mis = list(filter(lambda M:
                            infra.nodes[M]['cpu'] >= ns.nodes[n]['cpu'], Mis))
                    # Filter by possible location constraints
                    if 'location_constraints' in ns.nodes[n]:
                        Mis = list(filter(lambda M:
                            M in ns.nodes[n]['location_constraints'], Mis))

                    # Impossible to migrate
                    if not len(Mis) > 0:
                        # print(f'\tcould not migrate {n}')
                        success = False
                        break
                    else:
                        migrations[n] = list(Mis)[0]
                        # print(f'\t{n} migrated to {migrations[n]}')

                    # mark n as migrated;
                    # n0 ← the VNF shares same edge with n & not been migrated
                    mapping['migrated'] += [n]
                n0 = set(ns.neighbors(n)).intersection(
                        set(ns.nodes).difference(
                            set(mapping['migrated']).union(
                                set(mapping['remain']))))

                # enqueue n0 to q;
                q += list(n0)

            if success:
                stop = True # in the paper there is an error, it sets to False
            else:
                i += 1
        ##################################
        ###### <- end migration loop
        ##################################
        print(f'exit migration loop with i={i}')


        # migration failure
        if not success:
            mapping['worked'] = False
            return mapping


        #################################
        # Reallocate migrated resources #
        #################################
        reallocated = []
        for n in mapping['migrated']:
            n_M = migrations[n]
            mapping[n] = n_M

            # Reassign CPUs
            infra.nodes[prev_mapping[n]]['cpu'] += ns.nodes[n]['cpu']
            infra.nodes[migrations[n]]['cpu'] -= ns.nodes[n]['cpu']

            #print(f'\tremaping vnf={n}')

            # Reassign bandwidth
            for n2 in set(ns.neighbors(n)).difference(set(reallocated)):
                #print(f'\t  vl {n,n2}')

                # Restore bandwidth in previous link
                vl = (n,n2) if (n,n2) in prev_mapping else (n2,n)
                for a,b in zip(prev_mapping[vl][:-1],
                        prev_mapping[vl][1:]):
                    if b not in infra[a]: # unexisting cell connection
                        continue
                    infra[a][b]['bandwidth'] += ns[n][n2]['bandwidth']

                # Consume bandwidth along the new links
                n2_M = migrations[n2] if n2 in migrations\
                        else prev_mapping[n2]
                # print(f'n_M={n_M}  n2_M={n2_M}')
                for a,b in zip(Ms[n_M][n2_M]['path'][:-1],
                        Ms[n_M][n2_M]['path'][1:]):
                    if a != b:
                        infra[a][b]['bandwidth'] -= ns[n][n2]['bandwidth']
                    else:
                        pass # note that 2 VNFs might be on same host

                mapping[vl] = Ms[n_M][n2_M]['path']

            reallocated += [n]

        mapping['worked'] = True

        return mapping


    def mapping_cost(self, infra: nx.classes.graph.Graph,
            ns: nx.classes.graph.Graph, mapping: dict) -> float:
        """Derives the cost associated to a mapping

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :adj: int: graph depth of "adjacent servers"
        :mapping: dict: mapping
        :returns: float: the mapping cost
        """
        return sum(map(lambda n:
                infra.nodes[mapping[n]]['cost'] * ns.nodes[n]['cpu'],
            ns.nodes))

    


