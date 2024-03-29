from abc import ABCMeta, abstractmethod
import networkx as nx
import sys
from itertools import islice
import json

class AbstractChecker(metaclass=ABCMeta):

    """Abstract class for Checkers that verify the format of network services
    and infrastructure graphs
    """

    @abstractmethod
    def check_infra(self, infra) -> bool:
        """Checks if the infrastructure graph has the correct format

        :infra: infrastructure graph
        :returns: bool: telling if it satisfies it or not

        """
        pass


    @abstractmethod
    def check_ns(self, ns) -> bool:
        """Checks if the network service graph has the correct format

        :ns: network service graph
        :returns: bool: telling if it satisfies it or not

        """
        pass


class CheckBasicDigraphs(AbstractChecker):

    """Checker for network services and infrastructure graphs as the shown
    below:
    
    >>> infra = nx.DiGraph()
    >>> cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
    >>> infra.add_node('h1', cpu=2, mem=16, disk=1024, rats=['LTE', 'MMW'],
            location=(39.1408046,-1.0795603), cost=cost)
    >>> infra.add_node('h2', cpu=1, mem=8, disk=512, cost=cost)
    >>> infra.add_edge('h1', 'h2', bw=100, delay=1, cost=30)

    >>> ns = nx.DiGraph()
    >>> ns.add_node('v1', cpu=1, mem=4, disk=100, rats=['LTE'],
            location={'center': (39.128380, -1.080805), 'radius': 20})
    >>> ns.add_node('v2', cpu=1, mem=1, disk=400)
    >>> ns.add_edge('v1', 'v2', bw=59, delay=100)


    """

    def __init__(self):
        pass

        
    def check_infra(self, infra: nx.classes.digraph.DiGraph) -> bool:
        """Checks if the infrastructure graph has the correct format

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :returns: bool: telling if it satisfies it or not

        """
        for node in infra.nodes():
            node_dict = infra.nodes[node]
            if 'cpu' not in node_dict or type(node_dict['cpu']) != int:
                print("'cpu' key not present in node", node,
                      "or not an int", file=sys.stderr)
                return False
            if 'mem' not in node_dict or type(node_dict['mem']) != int:
                print("'mem' key not present in node, or not an int",
                        file=sys.stderr)
                return False
            if 'disk' not in node_dict or type(node_dict['disk']) != int:
                print("'disk' key not present in node, or not an int",
                        file=sys.stderr)
                return False
            if 'rats' in node_dict and type(node_dict['rats']) != list:
                print("'rats' key does not reference a list",
                        file=sys.stderr)
                return False
            if 'location' in node_dict and (type(node_dict['location']) != tuple\
                    or type(node_dict['location'][0]) != float\
                    or type(node_dict['location'][1]) != float):
                print("'location' key does not reference a tuple of floats",
                    file=sys.stderr)
                return False
            if 'cost' not in node_dict or type(node_dict['cost']) != dict:
                print("'cost' key not inside host, or is not dictionary",
                        file=sys.stderr)
                return False
            elif 'cpu' not in node_dict['cost'] or (\
                    type(node_dict['cost']['cpu']) != float and\
                    type(node_dict['cost']['cpu']) != int):
                print("'cpu' key not inside h['cost'], or is not a number",
                        file=sys.stderr)
                return False
            elif 'mem' not in node_dict['cost'] or (\
                    type(node_dict['cost']['mem']) != float and\
                    type(node_dict['cost']['mem']) != int):
                print("'mem' key not inside h['cost'], or is not a number",
                        file=sys.stderr)
                return False
            elif 'disk' not in node_dict['cost'] or (\
                    type(node_dict['cost']['disk']) != float and\
                    type(node_dict['cost']['disk']) != int):
                print("'disk' key not inside h['cost'], or is not a number",
                        file=sys.stderr)
                return False




        for h1,h2 in infra.edges():
            edge_dict = infra[h1][h2]
            if 'bw' not in edge_dict or type(edge_dict['bw']) != int:
                print("'bw' key not in physical link, or is not int",
                        file=sys.stderr)
                return False
            if 'delay' not in edge_dict or\
                    not isinstance(edge_dict['delay'], (int,float)):
                print("'delay' key not in physical link, or is not int|float",
                        file=sys.stderr)
                return False
            if 'cost' not in edge_dict or (type(edge_dict['cost']) != int\
                    and type(edge_dict['cost']) != float):
                print("'cost' key not inside h[h1][h2]['cost'],"+\
                        " or is not a number", file=sys.stderr)
                return False

        return True


    def check_ns(self, ns: nx.classes.digraph.DiGraph) -> bool:
        """Checks if the network service graph has the correct format

        :ns: nx.classes.digraph.DiGraph: network service graph
        :returns: bool: telling if it satisfies it or not

        """

        for node in ns.nodes():
            node_dict = ns.nodes[node]
            if 'cpu' not in node_dict or type(node_dict['cpu']) != int:
                print("'cpu' key not present in node, or not an int",
                        file=sys.stderr)
                return False
            if 'mem' not in node_dict or type(node_dict['mem']) != int:
                print("'mem' key not present in node, or not an int",
                        file=sys.stderr)
                return False
            if 'disk' not in node_dict or type(node_dict['disk']) != int:
                print("'disk' key not present in node, or not an int",
                        file=sys.stderr)
                return False
            if 'rats' in node_dict and type(node_dict['rats']) != list:
                print("'rats' key does not reference a list",
                        file=sys.stderr)
                return False
            if 'location' in node_dict:
                if type(node_dict['location']) != dict:
                    print("'location' key does not reference a dictionary",
                        file=sys.stderr)
                    return False
                if 'radius' not in node_dict['location'] or\
                        (type(node_dict['location']['radius']) != int and\
                        type(node_dict['location']['radius']) != float):
                    print("'location' does not have a 'radius', or it is not"+\
                            " a number", file=sys.stderr)
                    return False
                if 'center' not in node_dict['location'] or\
                        type(node_dict['location']['center']) != tuple or\
                        not isinstance(node_dict['location']['center'][0],
                                        (int, float)) or\
                        not isinstance(node_dict['location']['center'][1],
                                        (int, float)):
                    print(node_dict['location'])
                    print('node=%s' % node)
                    print(type(node_dict["location"]["center"]))
                    print("'location' does not have a 'center', or it is not"+\
                            " a tuple of floats", file=sys.stderr)
                    return False

        for h1,h2 in ns.edges():
            edge_dict = ns[h1][h2]
            if 'bw' not in edge_dict or type(edge_dict['bw']) != int:
                print("'bw' key not in virtual link, or is not int",
                        file=sys.stderr)
                return False
            if 'delay' not in edge_dict or type(edge_dict['delay']) != int:
                print("'delay' key not in virtual link, or is not int",
                        file=sys.stderr)
                return False

        return True



class CheckFogDigraphs(AbstractChecker):

    """Checks that the network services and infrastructures graphs are Basic
    digraphs with lifetime and reliability parameters."""

    def __init__(self):
        pass

        
    def check_infra(self, infra: nx.classes.digraph.DiGraph) -> bool:
        """Checks if the infrastructure graph has the correct format

        :infra: nx.classes.digraph.DiGraph: infrastructure graph
        :returns: bool: telling if it satisfies it or not

        """
        basic_checker = CheckBasicDigraphs()
        if not basic_checker.check_infra(infra):
            return False

        for h1,h2,e_d in infra.edges(data=True):
            if 'reliability' not in e_d:
                print("'reliability key not present in infrastructure",
                       "edge (", h1, h2, ")'", file=sys.stderr)
                return False

            for host in [h1, h2]:
                if 'reliability' not in infra.nodes[host]:
                    print("'reliability key not present in infrastructure"
                          " host", host, file=sys.stderr)
                    return False

                if 'lifetime' not in infra.nodes[host]:
                    print("'lifetime key not present in infrastructure host'",
                          host, file=sys.stderr)
                    return False

        return True


    def check_ns(self, ns: nx.classes.digraph.DiGraph,
                 check_vcore_Mb: bool=False) -> bool:
        """Checks if the network service graph has the correct format

        :ns: nx.classes.digraph.DiGraph: network service graph
        :check_vcore_Mb: bool: specify if vcore/Mb is mandatory on each VNF
        :returns: bool: telling if it satisfies it or not

        """
        basic_checker = CheckBasicDigraphs()

        # If mandatory, check if all VNFs specify 'vcore_per_Mb'
        missing_vcore_per_mb = False
        vcore_per_mbs = map(lambda v: ('vcore_per_Mb' in ns.nodes[v], v),
                            ns.nodes)
        for has_vcore_per_mb, v in list(vcore_per_mbs):
            if not has_vcore_per_mb:
                missing_vcore_per_mb = True
                msg_type = 'WARNING' if not check_vcore_Mb else 'ERROR'
                print('%s: vnf %s does not specify vcore_per_Mb'\
                        % (msg_type, v))
        if check_vcore_Mb and missing_vcore_per_mb:
            return False

        return basic_checker.check_ns(ns)














class CheckBasicGraphs(AbstractChecker):

    """Checker for network services and infrastructure graphs as the shown
    below, where a minimal set of keys is specified for a fog-cloud scenario.
    
    >>> infra = nx.Graph()
    >>> # cost relates to cpu/bandwidth costs
    >>> infra.add_node(1, name='robot_sq1_fogNode_1',
            cpu=2, lat=39.1408046, lon=-1.0795603, cost=238,
            type='fogNode')
    >>> infra.add_node(2, name='cell_2',
            cpu=2, lat=39.1408046, lon=-1.0795603, cost=238,
            type='cell')
    >>> infra.add_node(3, name='edge_server_server_3',
            cpu=20, lat=39.1408046, lon=-1.0795603, cost=238,
            type='server')
    >>> infra.add_node(4, name='m1_switch',
            cpu=0, lat=39.1408046, lon=-1.0795603, cost=238,
            type='m1')
    >>> infra.add_node(5, name='m2_switch',
            cpu=0, lat=39.1408046, lon=-1.0795603, cost=238,
            type='m2')
    >>> infra.add_node(6, name='cloud_server_server_0',
            cpu=0, lat=39.1408046, lon=-1.0795603, cost=238,
            type='cloud')
    >>> infra.add_edge(1, 2, bandwidth=100, delay=1)
    >>> infra.add_edge(2, 3, bandwidth=100, delay=1)
    >>> infra.add_edge(2, 4, bandwidth=100, delay=1)
    >>> infra.add_edge(4, 5, bandwidth=100, delay=1)
    >>> infra.add_edge(5, 6, bandwidth=100, delay=1)


    >>> ns = nx.Graph()
    >>> # some VNFs may require location constraints, be inside id=1
    >>> ns.add_node(1, cpu=0.1, location=[1])
    >>> ns.add_node(2, cpu=2)
    >>> ns.add_edge(1, 2, bandwidth=3)


    """

    def __init__(self):
        pass

        
    def check_infra(self, infra: nx.classes.graph.Graph) -> bool:
        """Checks if the infrastructure graph has the correct format

        :infra: nx.classes.graph.Graph: infrastructure graph
        :returns: bool: telling if it satisfies it or not

        """
        for node in infra.nodes():
            node_dict = infra.nodes[node]
            if 'cpu' not in node_dict or\
                    type(node_dict['cpu']) not in (int,float):
                print("'cpu' key not present in node", node,
                      "or not an int|float", file=sys.stderr)
                return False
            if 'cost' not in node_dict or\
                    type(node_dict['cost']) not in [float, int]:
                print("'cost' key not inside host, or is not float|int",
                        file=sys.stderr)
                return False
            if 'type' not in node_dict or type(node_dict['type']) != str:
                print("'type' key not inside host, or is not a str",
                        file=sys.stderr)
                return False
            if 'name' not in node_dict or type(node_dict['name']) != str:
                print("'name' key not inside host, or is not a str",
                        file=sys.stderr)
                return False



        for h1,h2 in infra.edges():
            edge_dict = infra[h1][h2]
            if 'bandwidth' not in edge_dict or\
                    type(edge_dict['bandwidth']) != int:
                print("'bandwidth' key not in physical link, or is not int",
                        file=sys.stderr)
                return False
            if 'delay' not in edge_dict or\
                    not isinstance(edge_dict['delay'], (int,float)):
                print("'delay' key not in physical link, or is not int|float",
                        file=sys.stderr)
                return False

        return True


    def check_ns(self, ns: nx.classes.graph.Graph) -> bool:
        """Checks if the network service graph has the correct format

        :ns: nx.classes.graph.Graph: network service graph
        :returns: bool: telling if it satisfies it or not

        """

        for node in ns.nodes():
            node_dict = ns.nodes[node]
            if 'cpu' not in node_dict or\
                    type(node_dict['cpu']) not in [float, int]:
                print("'cpu' key not present in node, or not an int|float",
                        file=sys.stderr)
                return False


        for h1,h2 in ns.edges():
            edge_dict = ns[h1][h2]
            if 'bandwidth' not in edge_dict or\
                    type(edge_dict['bandwidth']) != int:
                print(edge_dict)
                print("'bandwidth' key not in virtual link, or is not int",
                        file=sys.stderr)
                return False

        return True

