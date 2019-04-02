from abc import ABCMeta, abstractmethod
import networkx as nx
import sys
from itertools import islice

class AbstractMapper(metaclass=ABCMeta):

    """Abstract class for Mappers that perform VNF placements"""

    @abstractmethod
    def map(self, infra: nx.classes.graph.Graph,
            ns: nx.classes.graph.Graph) -> dict:
        """Maps a network service on top of an infrastructure.

        :infra: nx.classes.graph.Graph: infrastructure graph
        :ns: nx.classes.graph.Graph: network service graph
        :returns: dict: mapping decissions dictionary

        """
        pass


class GreedyCostMapper(AbstractMapper):

    """Mapper to minimize cost of placing the network service.
       It traverses the network service graph node by node, deciding at each
       step the mapping of the node and the edge that connects it with the
       next one. That is, it follows a greedy approach."""


    def __init__(self, k: int):
        """Initializes a Greedy Cost mapper

        :k: int: k shortest paths parameter for the virtual links steering

        """
        self.__k = k


    def __get_host(self, vnf, infra: nx.classes.graph.Graph):
        """Retrieve cheapest host in the infrastructure to place the vnf.

        :vnf: vnf dicrionary with its requirements
        :infra: nx.classes.graph.Graph: infrastructure graph
        :returns: identifier of best host

        """
        best_host, best_cost = None, sys.maxsize
        host_cpu = infra.nodes[host]['cpu']
        host_mem = infra.nodes[host]['mem']
        host_disk = infra.nodes[host]['disk']

        # Filter RAT capable hosts
        hosts = list(infra.nodes())
        if 'rat' in ns[vnf]:
            hosts = filter(lambda h: 'rats' in infra.nodes[h] and\
                vnf['rat'] in infra.nodes[host]['rats'], hosts)

        for host in rat_hosts:
            if host_cpu >= vnf['cpu'] and\
                    host_mem >= vnf['mem'] and\
                    host_disk >= vnf['disk']:

                host_cost = host_cost['cpu'] * vnf['cpu'] +\
                        host_cost['mem'] * vnf['mem'] +\
                        host_cost['disk'] * vnf['disk']
                
                if host_cost < best_cost:
                    best_host = host
                    best_cost = host_cost
        
        return best_host


    def __consume_vnf(self, host, vnf, infra: nx.classes.graph.Graph,
            ns: nx.classes.graph.Graph) -> None:
        """Consumes host's resources based on vnf resources

        :host: host identifier
        :vnf: vnf identifier within the graph
        :infra: nx.classes.graph.Graph: infrastructure graph
        :ns: nx.classes.graph.Graph: network service graph
        :returns: None

        """
        infra.nodes[host]['cpu'] -= ns.nodes[vnf]['cpu']
        infra.nodes[host]['mem'] -= ns.nodes[vnf]['mem']
        infra.nodes[host]['disk'] -= ns.nodes[vnf]['disk']
        infra.nodes[host]['rat_units'] -= ns.nodes[vnf]['rat_units']


    def __get_path(self, vl: dict, src_host, dst_host,
            infra: nx.classes.graph.Graph) -> dict:
        """Obtains a path to steer the vl accross the infrastructure,
        satisfying bandwidth and delay constraints.
        It looks for the cheapest path.

        :vl: dict: dictionary with the virtual link requirements
        :src_host: identifier of the host where the vl starts
        :dst_host: identifier of the host where the vl ends 
        :infra: nx.classes.graph.Graph: infrastructure graph
        :returns: dict: {'cost', 'path': [h1, ..., hn]}, or {} if fails

        """
        # Prune links not meeting bandwidth and delay requirements
        pruned_infra = infra.copy()
        pruned_links = [(h1,h2) for h1,h2 in pruned_infra.edges()\
                if pruned_infra[h1][h2]['bw'] < vl['bw'] or\
                    pruned_infra[h1][h2]['delay'] > vl['delay']]
        pruned_infra.remove_edges_from(pruned_links)

        all_shortest = nx.all_shortest_paths(pruned_infra,
                src_host, dst_host, weight='cost')
        best_path, best_cost = None, sys.maxsize
        for path in islice(all_shortest, self.__k)):
            cost, delay = 0, 0
            for h1,h2 in zip(path, path[1:]):
                cost += infra[h1][h2]['cost']
                delay += infra[h1][h2]['delay']

            if delay < vl['delay'] and cost < best_cost:
                best_cost = cost
                best_path = path

        return {'cost': best_cost, 'path': best_path}


    def map(self, infra: nx.classes.graph.Graph,
            ns: nx.classes.graph.Graph) -> dict:
        """Maps a network service on top of an infrastructure.

        :infra: nx.classes.graph.Graph: infrastructure graph
        :ns: nx.classes.graph.Graph: network service graph
        :returns: dict: mapping decissions dictionary

        """
        mapping = {
            'worked': True
        }

        infra_tmp = infra.copy()
        for vl in infra_tmp.edges():
            # Map the VNFs
            vnf1, vnf2 = vl
            for vnf in vl:
                host = self.__get_host(vnf, infra_tmp)
                if not host:
                    mapping['worked'] = False
                    return mapping
                else:
                    mapping[vnf] = host
                    self.__consume_vnf(host, vnf, infra, ns)

            # TODO
            self.__get_path(vl=next_vl, src_host=mapping[vnf1],
                    dst_host=mapping[vnf2], infra=infra_tmp)
    


