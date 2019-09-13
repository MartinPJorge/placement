import simulator.generate_service as gs
import placement.constructive_mapper_from_fractional as cmf
import networkx as nx


if __name__ == '__main__':
    substrate_network = gs.InfrastructureGMLGraph(gml_file="large-infra.gml", label='id')
    # TODO: simulator repeats this cycle multiple times with different service generation parameters.
    for seed in range(10):
        for spd_prob in range(1,10):
            try:
                service_instance = gs.ServiceGMLGraph(substrate_network, [50,15,40], seed, spd_prob/10.0)
                print("\n\nSEED: {}, series-parallel ratio: {}".format(seed, spd_prob/10.0))
                checker = cmf.VolatileResourcesChecker()
                mapper = cmf.ConstructiveMapperFromFractional(checker)
                mapper.map(substrate_network, service_instance)
            except cmf.UnfeasibleBinPacking:
                print("Bin packing is infeasible")
    # NOTE: forcing the algorithm to introduce new bin example: setting all item cost to 900, setting node 42 from 780 to 1200 cap, and node 47 from 10000 to 1000
    # service_instance = gs.ServiceGMLGraph(substrate_network, [7], 0, 0.5)
    # checker = cmf.VolatileResourcesChecker()
    # mapper = cmf.ConstructiveMapperFromFractional(checker)
    # mapper.map(substrate_network, service_instance)
