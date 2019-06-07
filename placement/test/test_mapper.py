import json
import unittest
import copy
import checker
import mapper
import networkx as nx

class TestGreedyCostMapper(unittest.TestCase):

    """Test case for the GreedyCostMapper class"""


    def setUp(self):
        # Create the infrastructure graph
        infra = nx.DiGraph()
        a_cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
        sw_cost = {'cpu': 0, 'disk': 0, 'mem': 0}
        h1_cost = {'cpu': 2, 'disk': 3, 'mem': 4}
        h2_cost = {'cpu': 1.5, 'disk': 2, 'mem': 2.1}
        antenna_jarafuel = infra.add_node('a-jara', cpu=2, mem=16, disk=1024,
                rats=['LTE', 'MMW'], location=(39.1408046,-1.0795603),
                cost=a_cost)
        antenna_jalance = infra.add_node('a-jala', cpu=2, mem=16, disk=1024,
                rats=['gsm'], location=(39.1906896,-1.0795596),
                cost=a_cost)
        switch1 = infra.add_node('sw1', cpu=0, mem=8, disk=512, cost=sw_cost)
        switch2 = infra.add_node('sw2', cpu=0, mem=8, disk=512, cost=sw_cost)
        switch3 = infra.add_node('sw3', cpu=0, mem=8, disk=512, cost=sw_cost)
        switch4 = infra.add_node('sw4', cpu=0, mem=8, disk=512, cost=sw_cost)
        infra.add_node('h1', cpu=1, mem=8, disk=512, cost=h1_cost)
        infra.add_node('h2', cpu=1, mem=8, disk=512, cost=h2_cost)
        infra.add_edge('a-jara', 'sw1', bw=100, delay=1, cost=20)
        infra.add_edge('a-jala', 'sw1', bw=100, delay=1, cost=20)
        infra.add_edge('sw1', 'sw2', bw=100, delay=1, cost=40)
        infra.add_edge('sw1', 'sw4', bw=100, delay=1, cost=20)
        infra.add_edge('sw4', 'sw3', bw=100, delay=1, cost=20)
        infra.add_edge('sw2', 'sw3', bw=100, delay=1, cost=20)
        infra.add_edge('sw1', 'h1', bw=100, delay=1, cost=20)
        infra.add_edge('sw3', 'h2', bw=100, delay=1, cost=20)
        self.infra = infra
        
        # Create the network service graph
        ns = nx.DiGraph()
        ns.add_node('vBBU', cpu=1, mem=4, disk=100, rats=['LTE'],
            location={'center': (39.128380, -1.080805), 'radius': 20})
        ns.add_node('vCache', cpu=1, mem=1, disk=400)
        ns.add_edge('vBBU', 'vCache', bw=59, delay=100)
        self.ns = ns

        # Instantiate a GreedyCostMapper
        self.checker = checker.CheckBasicDigraphs()
        self.mapper = mapper.GreedyCostMapper(checker=self.checker, k=2)


    def test_map(self):
        # Check unfeasible mapping - no LTE
        no_lte = copy.deepcopy(self.infra)
        del no_lte.nodes['a-jara']['rats'][0] # delete LTE
        mapping = self.mapper.map(infra=no_lte, ns=self.ns)
        self.assertFalse(mapping['worked'])
        
        # Check unfeasible mapping - slow links
        slow_links = copy.deepcopy(self.infra)
        links = slow_links.edges()
        for a,b in links:
            slow_links[a][b]['delay'] = 60
        mapping = self.mapper.map(infra=slow_links, ns=self.ns)
        self.assertEqual(mapping['vBBU'], 'a-jara')
        self.assertEqual(mapping['vCache'], 'h2')
        self.assertFalse(mapping['worked'])

        # Check correct mapping
        mapping = self.mapper.map(infra=self.infra, ns=self.ns)
        self.assertTrue(mapping['worked'])
        self.assertEqual(mapping['vBBU'], 'a-jara')
        self.assertEqual(mapping['vCache'], 'h2')
        self.assertEqual(mapping['vBBU', 'vCache'], ['a-jara', 'sw1',
            'sw4','sw3', 'h2'])


class TestGreedyFogCostMapper(unittest.TestCase):

    """Test case for the GreedyFogCostMapper class"""


    def __graphs_setup(self) -> None:
        """Create the infrastructure and network service graphs
        :returns: None

        """
        # Create the infrastructure graph
        infra = nx.DiGraph()
        a_cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
        a2_cost = {'cpu': 4, 'disk': 4.6, 'mem': 8}
        sw_cost = {'cpu': 0, 'disk': 0, 'mem': 0}
        h_cost = {'cpu': 2, 'disk': 3, 'mem': 4}
        f_cost = {'cpu': 4, 'disk': 6, 'mem': 8}

        infra.add_node('a1', cpu=1, mem=16, disk=1024,
                       rats=['LTE', 'MMW'], location=(39.1408046,-1.0795603),
                       cost=a_cost, reliability=1, lifetime=100)
        infra.add_node('a2', cpu=1, mem=16, disk=1024,
                       rats=['LTE', 'MMW'], location=(39.1408046,-1.0795603),
                       cost=a_cost, reliability=1, lifetime=100)
        infra.add_node('sw1', cpu=0, mem=8, disk=512, cost=sw_cost,
                       reliability=1, lifetime=100)
        infra.add_node('sw2', cpu=0, mem=8, disk=512, cost=sw_cost,
                       reliability=1, lifetime=100)
        infra.add_node('h1', cpu=1, mem=8, disk=512, cost=h_cost,
                       reliability=1, lifetime=100)
        infra.add_node('f1', cpu=1, mem=8, disk=512, cost=f_cost,
                       reliability=1, lifetime=80,
                       location=(39.128380, -1.080805))
        infra.add_node('f2', cpu=1, mem=8, disk=512, cost=f_cost,
                       reliability=0.8, lifetime=80,
                       location=(39.128380, -1.080805))
        infra.add_node('f3', cpu=1, mem=8, disk=512, cost=f_cost,
                       reliability=1, lifetime=50,
                       location=(39.128380, -1.080805))

        # Fog-antennas' links
        infra.add_edge('f1', 'a1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f2', 'a1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f3', 'a1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f1', 'a2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f2', 'a2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f3', 'a2', bw=100, delay=1, cost=20, reliability=1)

        # Antenna-switches' links
        infra.add_edge('a1', 'sw1', bw=100, delay=1, cost=4, reliability=1/2)
        infra.add_edge('a1', 'sw2', bw=100, delay=1, cost=3, reliability=1/2)

        # *-hosts' links
        infra.add_edge('sw1', 'h1', bw=100, delay=1, cost=4, reliability=1/2)
        infra.add_edge('sw2', 'h1', bw=100, delay=1, cost=3, reliability=1/2)
        infra.add_edge('a1', 'h1', bw=100, delay=1, cost=20, reliability=1/5)
        infra.add_edge('a2', 'h1', bw=100, delay=1, cost=20, reliability=1/5)

        self.infra = infra
        
        # Create the network service graph
        ns = nx.DiGraph()
        ns.add_node('robot', cpu=1, mem=1, disk=400,
                    location={'center': (39.128380, -1.080805), 'radius': 1})
        ns.add_node('AP', cpu=1, mem=4, disk=100, rats=['LTE', 'MMW'],
            location={'center': (39.1408046,-1.0795603), 'radius': 2})
        ns.add_node('control', cpu=1, mem=4, disk=100)
        ns.add_edge('robot', 'AP', bw=1, delay=100)
        ns.add_edge('AP', 'control', bw=1, delay=100)
        self.ns = ns


    def __mapper_set_up(self) -> None:
        """Creates the greedy fog mappers for the tests
        :returns: None

        """
        self.checker = checker.CheckFogDigraphs()
        self.mapper_k1 = mapper.GreedyFogCostMapper(checker=self.checker, k=1)
        self.mapper_k2 = mapper.GreedyFogCostMapper(checker=self.checker, k=2)

    def __map_suite(self) -> None:
        """Performs the mapping of the network service(s) in the test
        :returns: None

        """
        pass
        self.mapping_k1 = self.mapper_k1.map(infra=self.infra, ns=self.ns)
        self.mapping_k2 = self.mapper_k2.map(infra=self.infra, ns=self.ns)


    def setUp(self):
        self.__graphs_setup()
        self.__mapper_set_up()
        self.__map_suite()


    def test_map(self):
        """Checks if the mappings work
        :returns: None

        """
        # Check correct mapping for depth k=1
        self.assertTrue(self.mapping_k1['worked'])
        self.assertEqual(self.mapping_k1['robot'], 'f1')
        self.assertEqual(self.mapping_k1['AP'], 'a1')
        self.assertEqual(self.mapping_k1['control'], 'h1')
        self.assertEqual(self.mapping_k1['robot', 'AP'], ['f1', 'a1'])
        self.assertEqual(self.mapping_k1['AP', 'control'], ['a1', 'sw1', 'h1'])

        # Check correct mapping for depth k=2
        self.assertTrue(self.mapping_k2['worked'])
        self.assertEqual(self.mapping_k2['robot'], 'f1')
        self.assertEqual(self.mapping_k2['AP'], 'a1')
        self.assertEqual(self.mapping_k2['control'], 'h1')
        self.assertEqual(self.mapping_k2['robot', 'AP'], ['f1', 'a1'])
        self.assertEqual(self.mapping_k2['AP', 'control'], ['a1', 'sw2', 'h1'])


    def test_reliability(self):
        """Checks if the mapping reliability retrieval works
        :returns: None

        """
        self.assertEqual(mapper.GreedyFogCostMapper.map_reliability(
                         infra=self.infra, mapping=self.mapping_k1), 1/4)
        self.assertEqual(mapper.GreedyFogCostMapper.map_reliability(
                         infra=self.infra, mapping=self.mapping_k2), 1/4)


    def test_lifetime(self):
        """Checks if lifetime retrieval works
        :returns: None

        """
        self.assertEqual(mapper.GreedyFogCostMapper.map_lifetime(
                         infra=self.infra, mapping=self.mapping_k1), 80)  
        self.assertEqual(mapper.GreedyFogCostMapper.map_lifetime(
                         infra=self.infra, mapping=self.mapping_k2), 80)  
        

class TestFPTASMapper(unittest.TestCase):

    """Test case for the FPTASMapper class"""


    def __graphs_setup(self) -> None:
        """Create the infrastructure and network service graphs
        :returns: None

        """
        # Create the infrastructure graph
        infra = nx.DiGraph()
        a_cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
        f_cost = {'cpu': 4, 'disk': 6, 'mem': 8}
        h_cost = {'cpu': 2, 'disk': 4, 'mem': 5}

        infra.add_node('e1', cpu=0, mem=0, disk=0, reliability=1,
                       lifetime=80, location=(39.1298611,-1.0851077),
                       cost=a_cost, endpoint=True)
        infra.add_node('e2', cpu=0, mem=0, disk=0, reliability=1,
                       lifetime=80, location=(39.1348251,-1.0928467),
                       cost=a_cost, endpoint=True)
        infra.add_node('f1', cpu=1, mem=8, disk=512, cost=f_cost,
                       reliability=1, lifetime=80,
                       location=(39.128380, -1.080805))
        infra.add_node('f2', cpu=1, mem=8, disk=512, cost=f_cost,
                       reliability=1, lifetime=80,
                       location=(39.132474, -1.087976))
        infra.add_node('a1', cpu=1, mem=16, disk=1024,
                       rats=['LTE', 'MMW'], location=(39.1408046,-1.0795603),
                       cost=a_cost, reliability=1, lifetime=100)
        infra.add_node('a2', cpu=1, mem=16, disk=1024,
                       rats=['LTE', 'MMW'], location=(39.1408046,-1.0795603),
                       cost=a_cost, reliability=1, lifetime=100)
        infra.add_node('a3', cpu=1, mem=16, disk=1024,
                       rats=['LTE', 'MMW'], location=(39.1408046,-1.0795603),
                       cost=a_cost, reliability=1, lifetime=100)
        infra.add_node('sw1', cpu=0, mem=0, disk=0,
                       reliability=1, lifetime=100, cost=a_cost)
        infra.add_node('sw2', cpu=0, mem=0, disk=0,
                       reliability=1, lifetime=100, cost=a_cost)
        infra.add_node('h1', cpu=0, mem=0, disk=0, cost=h_cost,
                       reliability=1, lifetime=100)
        infra.add_node('h2', cpu=0, mem=0, disk=0, cost=h_cost,
                       reliability=1, lifetime=100)

        # Endpoint-fog links
        infra.add_edge('e1', 'f1', bw=10000, delay=0, cost=0, reliability=1)
        infra.add_edge('f1', 'e1', bw=10000, delay=0, cost=0, reliability=1)
        infra.add_edge('e2', 'f2', bw=10000, delay=0, cost=0, reliability=1)
        infra.add_edge('f2', 'e2', bw=10000, delay=0, cost=0, reliability=1)

        # Fog-antennas' links
        infra.add_edge('f1', 'a1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('a1', 'f1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f2', 'a1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('a1', 'f2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('f1', 'a2', bw=100, delay=1, cost=10, reliability=0.8)
        infra.add_edge('a2', 'f1', bw=100, delay=1, cost=10, reliability=0.8)
        infra.add_edge('f2', 'a2', bw=100, delay=1, cost=10, reliability=0.8)
        infra.add_edge('a2', 'f2', bw=100, delay=1, cost=10, reliability=0.8)
        infra.add_edge('f1', 'a3', bw=100, delay=1, cost=5, reliability=0.7)
        infra.add_edge('a3', 'f1', bw=100, delay=1, cost=5, reliability=0.7)
        infra.add_edge('f2', 'a3', bw=100, delay=1, cost=5, reliability=0.7)
        infra.add_edge('a3', 'f2', bw=100, delay=1, cost=5, reliability=0.7)

        # Antenna-switches' links
        infra.add_edge('a1', 'sw1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('a1', 'sw2', bw=100, delay=1, cost=20, reliability=0.9)
        infra.add_edge('a2', 'sw1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('a2', 'sw2', bw=100, delay=1, cost=20, reliability=0.9)
        infra.add_edge('a3', 'sw1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('a3', 'sw2', bw=100, delay=1, cost=20, reliability=0.9)
        infra.add_edge('sw1', 'a1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('sw2', 'a1', bw=100, delay=1, cost=20, reliability=0.9)
        infra.add_edge('sw1', 'a2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('sw2', 'a2', bw=100, delay=1, cost=20, reliability=0.9)
        infra.add_edge('sw1', 'a3', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('sw2', 'a3', bw=100, delay=1, cost=20, reliability=0.9)

        # Switches and servers
        infra.add_edge('sw1', 'h1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('sw2', 'h2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('sw1', 'h1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('sw2', 'h2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('h1', 'sw1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('h2', 'sw2', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('h1', 'sw1', bw=100, delay=1, cost=20, reliability=1)
        infra.add_edge('h2', 'sw2', bw=100, delay=1, cost=20, reliability=1)

        # Add self links
        for c in infra.nodes():
            infra.add_edge(c, c, bw=float('inf'), delay=0, cost=0,
                    reliability=1)

        self.infra = infra
        
        # Create the network service graph
        ns = nx.DiGraph()
        ns.add_node('e1', cpu=0, mem=0, disk=0, lv=1, reliability=0.4,
                    delay=400,
                    location={'center': (39.1298611,-1.0851077),
                              'radius': 0.001})
        ns.add_node('robot_master', cpu=1, mem=1, disk=400, lv=1,
                    location={'center': (39.128380, -1.080805),
                              'radius': 0.001})
        ns.add_node('AP', cpu=1, mem=4, disk=100, rats=['LTE', 'MMW'], lv=1,
            location={'center': (39.1408046,-1.0795603), 'radius': 2})
        ns.add_node('robot_slave', cpu=1, mem=1, disk=400, lv=1,
                    location={'center': (39.132474, -1.087976),
                              'radius': 0.001})
        ns.add_node('e2', cpu=0, mem=0, disk=0, lv=1,
                    location={'center': (39.1348251,-1.0928467),
                              'radius': 0.001})
        ns.add_edge('e1', 'robot_master', bw=0, delay=100)
        ns.add_edge('robot_master', 'AP', bw=1, delay=100)
        ns.add_edge('AP', 'robot_slave', bw=1, delay=100)
        ns.add_edge('robot_slave', 'e2', bw=0, delay=100)
        self.ns = ns


    def __mapper_set_up(self) -> None:
        """Creates the greedy fog mappers for the tests
        :returns: None

        """
        self.checker = checker.CheckFogDigraphs()
        self.mapper = mapper.FPTASMapper(checker=self.checker,
                                         log_out='/tmp/fptas_test.log')

    def __map_suite(self) -> None:
        """Performs the mapping of the network service(s) in the test
        :returns: None

        """
        # e2e-delay=400, reliability=1
        self.ns.nodes['e1']['delay'] = 400
        self.ns.nodes['e1']['reliability'] = 0.99
        self.mapping_d400_r1_k1_t3_rel099 = self.mapper.map(infra=self.infra,
                                                             ns=self.ns, k=1,
                                                             tau=3, relax=1)

        # e2e-delay=400, reliability=0.5
        self.ns.nodes['e1']['delay'] = 400
        self.ns.nodes['e1']['reliability'] = 0.5
        self.mapping_d400_r1_k1_t3_rel05 = self.mapper.map(infra=self.infra,
                                                             ns=self.ns, k=1,
                                                             tau=3, relax=1)

        # e2e-delay=400, reliability=0.3
        self.ns.nodes['e1']['delay'] = 400
        self.ns.nodes['e1']['reliability'] = 0.3
        self.mapping_d400_r1_k1_t3_rel03 = self.mapper.map(infra=self.infra,
                                                             ns=self.ns, k=1,
                                                             tau=3, relax=1)


    def setUp(self):
        self.__graphs_setup()
        self.__mapper_set_up()
        self.__map_suite()


    def test_reliability(self):
        """Tests that the mapping reliabilities satisfy the imposed end to end
        reliability

        """
        rel099 = mapper.GreedyFogCostMapper.map_reliability(infra=self.infra,
                                    mapping=self.mapping_d400_r1_k1_t3_rel099)
        self.assertTrue(rel099 >= 0.99)

        rel05 = mapper.GreedyFogCostMapper.map_reliability(infra=self.infra,
                                    mapping=self.mapping_d400_r1_k1_t3_rel05)
        self.assertTrue(rel05 >= 0.5)

        rel03 = mapper.GreedyFogCostMapper.map_reliability(infra=self.infra,
                                    mapping=self.mapping_d400_r1_k1_t3_rel03)
        self.assertTrue(rel03 >= 0.3)


    def test_map(self):
        """Checks if the mappings work
        :returns: None

        """
        # # Check correct mapping for depth k=1
        # self.assertTrue(self.mapping_k1['worked'])
        # self.assertEqual(self.mapping_k1['robot'], 'f1')
        # self.assertEqual(self.mapping_k1['AP'], 'a1')
        # self.assertEqual(self.mapping_k1['control'], 'h1')
        # self.assertEqual(self.mapping_k1['robot', 'AP'], ['f1', 'a1'])
        # self.assertEqual(self.mapping_k1['AP', 'control'], ['a1', 'sw1', 'h1'])

        # # Check correct mapping for depth k=2
        # self.assertTrue(self.mapping_k2['worked'])
        # self.assertEqual(self.mapping_k2['robot'], 'f1')
        # self.assertEqual(self.mapping_k2['AP'], 'a1')
        # self.assertEqual(self.mapping_k2['control'], 'h1')
        # self.assertEqual(self.mapping_k2['robot', 'AP'], ['f1', 'a1'])
        # self.assertEqual(self.mapping_k2['AP', 'control'], ['a1', 'sw2', 'h1'])


    ##  def test_reliability(self):
    ##      """Checks if the mapping reliability retrieval works
    ##      :returns: None

    ##      """
    ##      self.assertEqual(mapper.GreedyFogCostMapper.map_reliability(
    ##                       infra=self.infra, mapping=self.mapping_k1), 1/4)
    ##      self.assertEqual(mapper.GreedyFogCostMapper.map_reliability(
    ##                       infra=self.infra, mapping=self.mapping_k2), 1/4)


if __name__ == "__main__":
    unittest.main()


