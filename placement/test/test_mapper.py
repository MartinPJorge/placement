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



if __name__ == "__main__":
    unittest.main()


