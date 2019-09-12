import simulator.generate_service as gs
from placement.constructive_mapper_from_fractional import VolatileResourcesChecker, ConstructiveMapperFromFractional
import networkx as nx


if __name__ == '__main__':
    substrate_network = gs.InfrastructureGMLGraph(gml_file="large-infra.gml", label='id')
    # TODO: simulator repeats this cycle multiple times with different service generation parameters.
    service_instance = gs.ServiceGMLGraph(substrate_network, [4,10,10,50,80, 100], 0, 0.5)
    checker = VolatileResourcesChecker()
    mapper = ConstructiveMapperFromFractional(checker)
    mapper.map(substrate_network, service_instance)
