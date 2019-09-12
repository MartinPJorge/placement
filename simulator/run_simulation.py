import simulator.generate_service as gs
import placement.constructive_mapper_from_fractional as cmf
import networkx as nx


if __name__ == '__main__':
    substrate_network = gs.InfrastructureGMLGraph(gml_file="large-infra.gml", label='id')
    # TODO: simulator repeats this cycle multiple times with different service generation parameters.
    for seed in range(10):
        for spd_prob in range(1,10):
            try:
                service_instance = gs.ServiceGMLGraph(substrate_network, [50,15,50,40,100], seed, spd_prob/10.0)
                print("\n\nSEED: {}, series-parallel ratio: {}".format(seed, spd_prob/10.0))
                checker = cmf.VolatileResourcesChecker()
                mapper = cmf.ConstructiveMapperFromFractional(checker)
                mapper.map(substrate_network, service_instance)
            except cmf.UnfeasibleBinPacking:
                pass
