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


    def setUp(self):
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
                       reliability=1, lifetime=100,
                       location=(39.128380, -1.080805))
        infra.add_node('f2', cpu=1, mem=8, disk=512, cost=f_cost,
                       reliability=0.8, lifetime=100,
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

        # Instantiate a GreedyCostMapper
        self.checker = checker.CheckFogDigraphs()
        self.mapper_k1 = mapper.GreedyFogCostMapper(checker=self.checker, k=1)
        self.mapper_k2 = mapper.GreedyFogCostMapper(checker=self.checker, k=2)


    def test_map(self):
        # Check correct mapping for depth k=1
        mapping = self.mapper_k1.map(infra=self.infra, ns=self.ns)
        self.assertTrue(mapping['worked'])
        self.assertEqual(mapping['robot'], 'f1')
        self.assertEqual(mapping['AP'], 'a1')
        self.assertEqual(mapping['control'], 'h1')
        self.assertEqual(mapping['robot', 'AP'], ['f1', 'a1'])
        self.assertEqual(mapping['AP', 'control'], ['a1', 'h1'])

        # Check correct mapping for depth k=2
        mapping = self.mapper_k1.map(infra=self.infra, ns=self.ns)
        self.assertTrue(mapping['worked'])
        self.assertEqual(mapping['robot'], 'f1')
        self.assertEqual(mapping['AP'], 'a1')
        self.assertEqual(mapping['control'], 'h1')
        self.assertEqual(mapping['robot', 'AP'], ['f1', 'a1'])
        self.assertEqual(mapping['AP', 'control'], ['a1', 'sw2', 'h1'])


if __name__ == "__main__":
    unittest.main()


