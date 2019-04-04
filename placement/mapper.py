from abc import ABCMeta, abstractmethod
from haversine import haversine
import copy
import networkx as nx
import sys
from itertools import islice
from checker import AbstractChecker
from functools import reduce

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
            for vnf in vl:
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


