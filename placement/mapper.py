from abc import ABCMeta, abstractmethod
from haversine import haversine
import copy
import networkx as nx
import sys
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
            reliab *= infra.nodes[mapping[vnf]]['reliability']

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

    """Maps a network service using a FPTAS modification of multiconstraint
       routing under path additive constraints. Algorithm 2 of [1]
       
       [1] Xue, Guoliang, et al. "Finding a path subject to many additive QoS
       constraints."
       IEEE/ACM Transactions on Networking (TON) 15.1 (2007): 201-211."""


    @abstractmethod
    def __init__(self, checker: CheckFogDigraphs, log_out: str):
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
        comp_nodes = set(infra.nodes())
        if src not in comp_nodes:
            comp_nodes.union(src)
        src_paths = {}

        # Find all paths between computational nodes
        for from_ in comp_nodes:
            src_paths[from_] = {}
            for to_ in [c for c in comp_nodes if c != to_]:
                for path in k_shortest_paths(infra, from_, to_,
                                             k=k, weight='delay'):
                    if to_ not in src_paths[from_]:
                        src_paths[from_][to_] = {
                            'paths': [],
                            'delays': [],
                            'reliabs': [],
                            'bw': []
                        }

                    # Calculate path delay and reliability
                    src_paths[from_][to_]['paths'] += [path]
                    delay, reliab, cost, bw = 0, 1, 0, sys.maxsize
                    for (n1,n2) in zip(path[:-1], path[1:]):
                        if infra[n1][n2]['bw'] < bw:
                            bw = infra[n1][n2]['bw']
                        delay += infra[n1][n2]['delay']
                        reliab *= infra[n1][n2]['reliability']
                        if n2 != to_:
                            reliab *= infra[n2]['reliability']
                        cost += infra[n1][n2]['trafficCost']
                    src_paths[from_][to_]['delays'] += [delay]
                    src_paths[from_][to_]['reliability'] += [reliab]
                    src_paths[from_][to_]['bw'] += [bw]
                    src_paths[from_][to_]['cost'] += [cost]


        # Build the auxiliary graph
        self.__aux_g = nx.DiGraph()
        for comp_node in comp_nodes:
            for tau_ in range(1, tau + 1):
                self.__aux_g.add_node((comp_node,tau_),
                                      **infra.nodes[comp_node])

        # Connect the auxiliary graph nodes
        for (c1,A) in self.__aux_g.nodes():
            for (c2,B) in self.__aux_g.nodes():
                if c1 == c2:
                    self.__aux_g.add_edge((c1,A), (c2,B), w1=0, delay=0)
                else:
                    w1 = -1 * tau * log(1/(infra[c1][c2]['reliability']*\
                                           infra[c2]['reliability']))\
                                    / log(ereliab)
                    if A + w1 <= B:
                        self.__aux_g.add_edge((c1,A), (c2,B), w1=w1,
                                              delay=infra[c1][c2]['delay'])


    def __ordered_vls(self, ns: nx.classes.digraph.DiGraph) -> list:
        """Obtain the ordered list of virtual links in a network service

        :ns: nx.classes.digraph.DiGraph:  network service graph
        :returns: list: [(vnf1, vnf2, {...}), ...]

        """
        start_vnf = list(filter(lambda vnf: ns.in_degree(vnf) == 0),
                                ns.nodes())[0]
        curr_vnf = start_vnf
        vls = []
        while len(ns[curr_vnf]) > 0:
            next_vnf = list(ns[curr_vnf])[0]
            vls += [(curr_vnf, next_vnf, ns[curr_vnf][next_vnf])]
            curr_vnf = next_vnf

        return vls


    @abstractmethod
    def map(self, infra: nx.classes.digraph.DiGraph,
            ns: nx.classes.digraph.DiGraph, k: int, tau: int) -> dict:
        """Maps a network service using a variation of [1]

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :ns: nx.classes.digraph.DiGraph: network service graph
        :k: int: number of shortest paths between computational nodes
        :tau: int: granularity, the higher, the more precise
        :returns: dict: mapping decissions dictionary

        """
        endpoint = list(filter(lambda vnf: ns.in_degree(vnf) == 0),
                               ns.nodes())[0]
        self.__build_aux(infra=infra, src=start_vnf, k=k, tau=tau,
                         ereliab=ns.nodes[start_vnf]['reliability'])
        vls = self.__ordered_vls(ns)
        hop_delay = [ns.nodes[endpoint]['delay'] / len(infra.nodes)]\
                    * len(infra.nodes)

        # Dictionaries to store cost and cpu as mapping advances
        cost = {
            (c,A,v1,v2): sys.maxsize
            for (c,A) in self.__aux_g.nodes()
            for (v1,v2) in vls
        }
        curr_cpu = {
            (c,A,v1,v2): infra.nodes[c]['cpu']
            for (c,A) in self.__aux_g.nodes()
            for (v1,v2) in vls
        }
        prev = {
            (c,A,v1,v2): None
            for (c,A) in self.__aux_g.nodes()
            for (v1,v2) in vls
        }

        # MAIN LOOP
        for hop in range(len(vls)):
            v1,v2,vl_d = vls[hop]
            v0 = None if hop == 0 else vls[hop-1][0]

            first_vl = v1 == endpoint
            to_visit = self.__aux_g.edges() if not first_vl else\
                       filter(lambda ((c0,A),(c2,B)): c0 == endpoint\
                                                      and A == 0,
                              self.__aux_g.edges())


            for ((c1,A),(c2,B),l_d) in filter(lambda ((c1,A),(c2,B),d):\
                                            d['bw'] >= vl_d['bw'], to_visit):
                need_cpu = ns.nodes[v2]['lv'] * vl_d['bw'] /\
                           (hop_delay[hop] - l_d['delay'])
                incur_cost = infra.nodes[c2]['resCost'] * need_cpu +\
                             self.__aux_g[(c1,A)][(c2,B)]['cost'] +\
                             (0 if first_vl else cost[(c1,A,v0,v1)])

                if curr_cpu[(c2,B,v1,v2)] >= need_cpu and\
                        incur_cost < cost[(c2,B,v1,v2)]:
                    cost[(c2,B,v1,v2)] = incur_cost
                    prev[(c2,B,v1,v2)] = (c1,A)

                    if hop + 1 < len(vls): # refresh CPU status for next iters
                        for c,B_ in map(lambda (c,B_): c==c2,
                                        self.__aux_g.nodes()):
                            _,v3 = vls[hop+1]
                            curr_cpu[(c,B_,v2,v3)] =\
                                    curr_cpu[(c2,B,v1,v2)] - need_cpu

            if any(map(lambda (c,A): cost[(c,A,v1,v2)] < sys.maxsize,
                       self.__aux_g.nodes())):
                pass # success mapping
            else:
                # decrease per-hop link delay


