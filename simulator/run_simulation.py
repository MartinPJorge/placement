import simulator.generate_service as gs
import networkx as nx


if __name__ == '__main__':
    substrate_network = gs.InfrastructureGMLGraph(gml_file="large-infra.gml", label='id')
    service_instance = gs.ServiceGMLGraph(substrate_network, [4,5,10], 0, 0.5)
    pass
