import unittest
import copy
import checker
import networkx as nx

class TestCheckBasicDigraphs(unittest.TestCase):

    """Test case for the CheckBasicDigraphs class"""

    def __infra_setUp(self):
        # Create properly formed graphs
        infra = nx.DiGraph()
        cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
        infra.add_node('h1', cpu=2, mem=16, disk=1024, rats=['LTE', 'MMW'],
            location=(39.1408046,-1.0795603), cost=cost)
        infra.add_node('h2', cpu=1, mem=8, disk=512, cost=cost)
        infra.add_edge('h1', 'h2', bw=100, delay=1, cost=20)

        self.infra_ok = infra
        
        ns = nx.DiGraph()
        ns.add_node('v1', cpu=1, mem=4, disk=100, rats=['LTE'],
            location={'center': (39.128380, -1.080805), 'radius': 20})
        ns.add_node('v2', cpu=1, mem=1, disk=400)
        ns.add_edge('v1', 'v2', bw=59, delay=100)
        self.ns_ok = ns
        
        # Infrastructure without cpu
        infra_no_cpu = copy.deepcopy(infra)
        del infra_no_cpu.nodes['h1']['cpu']
        self.infra_no_cpu = infra_no_cpu

        # Infrastructure with bad cpu
        infra_bad_cpu = copy.deepcopy(infra)
        infra_bad_cpu.nodes['h1']['cpu'] = 'a'
        self.infra_bad_cpu = infra_bad_cpu

        # Infrastructure without mem 
        infra_no_mem = copy.deepcopy(infra)
        del infra_no_mem.nodes['h1']['mem']
        self.infra_no_mem = infra_no_mem

        # Infrastructure with bad mem
        infra_bad_mem = copy.deepcopy(infra)
        infra_bad_mem.nodes['h1']['mem'] = 'a'
        self.infra_bad_mem = infra_bad_mem

        # Infrastructure without disk 
        infra_no_disk = copy.deepcopy(infra)
        del infra_no_disk.nodes['h1']['disk']
        self.infra_no_disk = infra_no_disk

        # Infrastructure with bad disk
        infra_bad_disk = copy.deepcopy(infra)
        infra_bad_disk.nodes['h1']['disk'] = 'a'
        self.infra_bad_disk = infra_bad_disk
        
        # Incorrect rats
        infra_bad_rats = copy.deepcopy(infra)
        infra_bad_rats.nodes['h1']['rats'] = ''
        self.infra_bad_rats = infra_bad_rats

        # Incorrect location type
        infra_bad_location1 = copy.deepcopy(infra)
        infra_bad_location1.nodes['h1']['location'] = ''
        self.infra_bad_location1 = infra_bad_location1

        # Incorrect location tuple
        infra_bad_location2 = copy.deepcopy(infra)
        infra_bad_location2.nodes['h1']['location'] = ('a', 2)
        self.infra_bad_location2 = infra_bad_location2

        # No host cost
        infra_no_host_cost = copy.deepcopy(infra)
        del infra_no_host_cost.nodes['h1']['cost']
        self.infra_no_host_cost = infra_no_host_cost

        # Bad cost 1
        infra_bad_cost1 = copy.deepcopy(infra)
        cost = {'mem': 2, 'disk': 3}
        infra_bad_cost1.nodes['h1']['cost'] = cost
        self.infra_bad_cost1 = infra_bad_cost1

        # Bad cost 2
        infra_bad_cost2 = copy.deepcopy(infra)
        cost = {'cost': '', 'mem': 2, 'disk': 3}
        infra_bad_cost2.nodes['h1']['cost'] = cost
        self.infra_bad_cost2 = infra_bad_cost2

        # Bad cost 3
        infra_bad_cost3 = copy.deepcopy(infra)
        cost = {'cpu': 2, 'disk': 3}
        infra_bad_cost3.nodes['h1']['cost'] = cost
        self.infra_bad_cost3 = infra_bad_cost3

        # Bad cost 4
        infra_bad_cost4 = copy.deepcopy(infra)
        cost = {'mem': '', 'cpu': 2, 'disk': 3}
        infra_bad_cost4.nodes['h1']['cost'] = cost
        self.infra_bad_cost4 = infra_bad_cost4

        # Bad cost 5
        infra_bad_cost5 = copy.deepcopy(infra)
        cost = {'cpu': 2, 'mem': 3}
        infra_bad_cost5.nodes['h1']['cost'] = cost
        self.infra_bad_cost5 = infra_bad_cost5

        # Bad cost 4
        infra_bad_cost6 = copy.deepcopy(infra)
        cost = {'disk': '', 'cpu': 2, 'mem': 3}
        infra_bad_cost6.nodes['h1']['cost'] = cost
        self.infra_bad_cost6 = infra_bad_cost6

        # No bandwidth
        infra_no_bw = copy.deepcopy(infra)
        del infra_no_bw['h1']['h2']['bw']
        self.infra_no_bw = infra_no_bw

        # Bad bandwidth
        infra_bad_bw = copy.deepcopy(infra)
        infra_bad_bw['h1']['h2']['bw'] = ''
        self.infra_bad_bw = infra_bad_bw

        # No delay
        infra_no_delay = copy.deepcopy(infra)
        del infra_no_delay['h1']['h2']['delay']
        self.infra_no_delay = infra_no_delay

        # Bad delay 
        infra_bad_delay = copy.deepcopy(infra)
        infra_bad_delay['h1']['h2']['delay'] = ''
        self.infra_bad_delay = infra_bad_delay

        # No cost
        infra_no_cost = copy.deepcopy(infra)
        del infra_no_cost['h1']['h2']['cost']
        self.infra_no_cost = infra_no_cost

        # Bad cost
        infra_bad_cost = copy.deepcopy(infra)
        infra_bad_cost['h1']['h2']['cost'] = ''
        self.infra_bad_cost = infra_bad_cost


    def __ns_setUp(self):
        ns = nx.DiGraph()
        ns.add_node('v1', cpu=1, mem=4, disk=100, rats=['LTE'],
            location={'center': (39.128380, -1.080805), 'radius': 20})
        ns.add_node('v2', cpu=1, mem=1, disk=400)
        ns.add_edge('v1', 'v2', bw=59, delay=100)
        self.ns_ok = ns

        # Without cpu
        ns_no_cpu = copy.deepcopy(ns)
        del ns_no_cpu.nodes['v1']['cpu']
        self.ns_no_cpu = ns_no_cpu

        # Incorrect cpu
        ns_bad_cpu = copy.deepcopy(ns)
        ns_bad_cpu.nodes['v1']['cpu'] = ('a', 2)
        self.ns_bad_cpu = ns_bad_cpu

        # Without mem
        ns_no_mem = copy.deepcopy(ns)
        del ns_no_mem.nodes['v1']['mem']
        self.ns_no_mem = ns_no_mem

        # Incorrect mem
        ns_bad_mem = copy.deepcopy(ns)
        ns_bad_mem.nodes['v1']['mem'] = ('a', 2)
        self.ns_bad_mem = ns_bad_mem

        # Without disk
        ns_no_disk = copy.deepcopy(ns)
        del ns_no_disk.nodes['v1']['disk']
        self.ns_no_disk = ns_no_disk

        # Incorrect rats
        ns_bad_rats = copy.deepcopy(ns)
        ns_bad_rats.nodes['v1']['rats'] = ('a', 2)
        self.ns_bad_rats = ns_bad_rats

        # Incorrect disk
        ns_bad_disk = copy.deepcopy(ns)
        ns_bad_disk.nodes['v1']['disk'] = ('a', 2)
        self.ns_bad_disk = ns_bad_disk

        # Incorrect location1
        ns_bad_location1 = copy.deepcopy(ns)
        ns_bad_location1.nodes['v1']['location'] = ('a', 2)
        self.ns_bad_location1 = ns_bad_location1
        
        # Incorrect location2
        ns_bad_location2 = copy.deepcopy(ns)
        ns_bad_location2.nodes['v1']['location'] = {'radius': 20}
        self.ns_bad_location2 = ns_bad_location2
        
        # Incorrect location3
        ns_bad_location3 = copy.deepcopy(ns)
        ns_bad_location3.nodes['v1']['location'] = {
                'radius': 'a', 'center': (2.2,2.2)}
        self.ns_bad_location3 = ns_bad_location3
        
        # Incorrect location4
        ns_bad_location4 = copy.deepcopy(ns)
        ns_bad_location4.nodes['v1']['location'] = {'radius': 20, 'center': 3}
        self.ns_bad_location4 = ns_bad_location3

        # No bandwidth
        ns_no_bw = copy.deepcopy(ns)
        del ns_no_bw['v1']['v2']['bw']
        self.ns_no_bw = ns_no_bw

        # Bad bandwidth
        ns_bad_bw = copy.deepcopy(ns)
        ns_bad_bw['v1']['v2']['bw'] = ''
        self.ns_bad_bw = ns_bad_bw

        # No delay
        ns_no_delay = copy.deepcopy(ns)
        del ns_no_delay['v1']['v2']['delay']
        self.ns_no_delay = ns_no_delay

        # Bad delay 
        ns_bad_delay = copy.deepcopy(ns)
        ns_bad_delay['v1']['v2']['delay'] = ''
        self.ns_bad_delay = ns_bad_delay


    def setUp(self):
        """Creates the testing network service and infrastructure graph
        :returns: None

        """
        self.basic_di_checker = checker.CheckBasicDigraphs()
        self.__infra_setUp()
        self.__ns_setUp()


    def test_infra_location(self):
        self.assertFalse(self.basic_di_checker.check_infra(
            self.infra_bad_location1))
        self.assertFalse(self.basic_di_checker.check_infra(
            self.infra_bad_location2))

    def test_infra_cpu(self):
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_no_cpu))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cpu))

    def test_infra_mem(self):
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_no_mem))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_mem))

    def test_infra_disk(self):
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_no_disk))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_disk))

    def test_infra_rats(self):
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_rats))

    def test_infra_delay(self):
        self.assertFalse(self.basic_di_checker.check_infra(
            self.infra_bad_delay))
        self.assertFalse(self.basic_di_checker.check_infra(
            self.infra_no_delay))

    def test_infra_bw(self):
        self.assertFalse(self.basic_di_checker.check_infra(
            self.infra_bad_bw))
        self.assertFalse(self.basic_di_checker.check_infra(
            self.infra_no_bw))
    
    def test_bad_cost(self):
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost1))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost2))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost3))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost4))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost5))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_bad_cost6))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_no_cost))
        self.assertFalse(self.basic_di_checker.check_infra(self.infra_no_host_cost))

    def test_ns_cpu(self):
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_no_cpu))
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_cpu))

    def test_ns_mem(self):
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_no_mem))
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_mem))

    def test_ns_disk(self):
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_no_disk))
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_disk))

    def test_ns_rats(self):
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_rats))

    def test_ns_location(self):
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_location1))
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_location2))
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_location3))
        self.assertFalse(self.basic_di_checker.check_ns(self.ns_bad_location4))

    def test_ns_delay(self):
        self.assertFalse(self.basic_di_checker.check_ns(
            self.ns_bad_delay))
        self.assertFalse(self.basic_di_checker.check_ns(
            self.ns_no_delay))

    def test_ns_bw(self):
        self.assertFalse(self.basic_di_checker.check_ns(
            self.ns_bad_bw))
        self.assertFalse(self.basic_di_checker.check_ns(
            self.ns_no_bw))

    def test_ok(self):
        self.assertTrue(self.basic_di_checker.check_ns(self.ns_ok))
        self.assertTrue(self.basic_di_checker.check_infra(self.infra_ok))


class TestCheckFogDigraphs(unittest.TestCase):

    """Test case for the CheckFogDigraphs class"""

    def __infra_setUp(self):
        # Create properly formed graphs
        infra = nx.DiGraph()
        cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
        infra.add_node('h1', cpu=2, mem=16, disk=1024, rats=['LTE', 'MMW'],
                       location=(39.1408046,-1.0795603), cost=cost,
                       reliability=1, lifetime=10)
        infra.add_node('h2', cpu=1, mem=8, disk=512, cost=cost, reliability=1,
                       lifetime=10)
        infra.add_edge('h1', 'h2', bw=100, delay=1, cost=20, reliability=1)

        self.infra_ok = infra
        
        # h1 without reliability
        infra_no_host_reliab = copy.deepcopy(infra)
        del infra_no_host_reliab.nodes['h1']['reliability']
        self.infra_no_host_reliab = infra_no_host_reliab
        
        # h1 without lifetime 
        infra_no_host_lifetime = copy.deepcopy(infra)
        del infra_no_host_lifetime.nodes['h1']['lifetime']
        self.infra_no_host_lifetime = infra_no_host_lifetime

        # No edge reliability
        infra_no_edge_reliab = copy.deepcopy(infra)
        del infra_no_edge_reliab['h1']['h2']['reliability']
        self.infra_no_edge_reliab = infra_no_edge_reliab


    def setUp(self):
        """Creates the testing network service and infrastructure graph
        :returns: None

        """
        self.fog_di_checker = checker.CheckFogDigraphs()
        self.__infra_setUp()


    def test_infra(self):
        self.assertTrue(self.fog_di_checker.check_infra(self.infra_ok))
        self.assertFalse(self.fog_di_checker.check_infra(
                         self.infra_no_host_lifetime))
        self.assertFalse(self.fog_di_checker.check_infra(
                         self.infra_no_host_reliab))
        self.assertFalse(self.fog_di_checker.check_infra(
                         self.infra_no_edge_reliab))




if __name__ == "__main__":
    unittest.main()


