import networkx as nx

import ampl.graph2ampl as graph2ampl
import graphs.generate_service as gs
import heuristic.placement.constructive_mapper_from_fractional as cmf


def run_some_tests(substrate_network):
    # TODO: simulator repeats this cycle multiple times with different service generation parameters.
    for seed in range(10):
        for spd_prob in range(1,10):
            try:
                print("\n\nSEED: {}, series-parallel ratio: {}".format(seed, spd_prob/10.0))
                service_instance = gs.ServiceGMLGraph(substrate_network,  connected_component_sizes=[50,15,40], sfc_delays=[0.01, 0.015],
                                                      seed=seed, series_parallel_ratio=spd_prob/10.0, name='service')
                checker = cmf.VolatileResourcesChecker()
                mapper = cmf.ConstructiveMapperFromFractional(checker)
                mapper.map(substrate_network, service_instance)

                # try:
                #     ampl_object = graph2ampl.get_complete_ampl_model_data('../ampl/system-model.mod',
                #                                                           service_instance, substrate_network)
                #     # TODO: second execution of ampl tranform gives exception on NOT unique 'cell1' -- internal AMPL object not created from scratch?
                #     # TODO: invoke AMPL solver and extract solution
                # except Exception:
                #     print("Error in parsing")
                #     raise

            except cmf.UnfeasibleBinPacking:
                print("Bin packing is infeasible")


if __name__ == '__main__':
    substrate_network = gs.InfrastructureGMLGraph(gml_file="../graphs/infra-2-clusters-20-cells.gml", label='id', name='infra',
                                                  cluster_move_distances=[0.002, 0.005], time_interval_count=12)

    # NOTE: forcing the algorithm to introduce new bin example: setting all item cost to 900, setting node 42 from 780 to 1200 cap, and node 47 from 10000 to 1000
    service_instance = gs.ServiceGMLGraph(substrate_network, [7], [0.01, 0.015], 0, 0.5, name='service')
    checker = cmf.VolatileResourcesChecker()
    mapper = cmf.ConstructiveMapperFromFractional(checker)
    mapper.map(substrate_network, service_instance)

    ampl_object = graph2ampl.get_complete_ampl_model_data('../ampl/system-model.mod',
                                                          service_instance, substrate_network)

    # run_some_tests(substrate_network)






