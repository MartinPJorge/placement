import sys
import argparse
import yaml
import os
import logging
from rainbow_logging_handler import RainbowLoggingHandler
sys.path.append(os.path.abspath(".."))

from ampl.ampl_support import AMPLSolverSupport
import graphs.generate_service as gs
import heuristic.placement.constructive_mapper_from_fractional as cmf


def run_some_tests(substrate_network):
    # TODO: simulator repeats this cycle multiple times with different service generation parameters.
    for seed in range(10):
        for spd_prob in range(1,10):
            try:
                print("\n\nSEED: {}, series-parallel ratio: {}".format(seed, spd_prob/10.0))
                service_instance = gs.ServiceGMLGraph(substrate_network, connected_component_sizes=[50,15], sfc_delays=[0.01, 0.015],
                                                      seed=seed, series_parallel_ratio=spd_prob/10.0, mobile_nfs_per_sfc=2, name='service')
                checker = cmf.VolatileResourcesChecker()
                mapper = cmf.ConstructiveMapperFromFractional(checker)
                mapper.map(substrate_network, service_instance)

                # try:
                #     ampl_solver_support = graph2ampl.get_complete_ampl_model_data('../ampl/system-model.mod',
                #                                                           service_instance, substrate_network)
                #     # TODO: second execution of ampl tranform gives exception on NOT unique 'cell1' -- internal AMPL object not created from scratch?
                #     # TODO: invoke AMPL solver and extract solution
                # except Exception:
                #     print("Error in parsing")
                #     raise

            except cmf.UnfeasibleBinPacking:
                print("Bin packing is infeasible")


def test_delay_calc(substrate_network, time_interval_count):
    # tests the delay calculation
    for t in range(1,time_interval_count + 1):
        for u in substrate_network.nodes():
            for v in substrate_network.nodes():
                print(u, v, t, 0.5, substrate_network.delay_distance(u, v, t, coverage_prob=0.5))
                for ap_id in substrate_network.access_point_ids:
                    print(u, v, t, ap_id, substrate_network.delay_distance(u, v, t, through_ap_id=ap_id))


def run_without_config_file():
    time_interval_count = 12
    substrate_network = gs.InfrastructureGMLGraph(gml_file="../graphs/infras/cobo-calleja/pico-and-micro-cobo-calleja.gml", label='id', name='infra',
                                                  cluster_move_distances=[0.002, 0.005], time_interval_count=time_interval_count)

    # NOTE: forcing the algorithm to introduce new bin example: setting all item cost to 900, setting node 42 from 780 to 1200 cap, and node 47 from 10000 to 1000
    service_instance = gs.ServiceGMLGraph(substrate_network, [7], [0.01, 0.015], 0, 0.5, name='service')
    checker = cmf.VolatileResourcesChecker()
    try:
        mapper = cmf.ConstructiveMapperFromFractional(checker)
        mapper.map(substrate_network, service_instance)
    except cmf.UnfeasibleBinPacking:
        print("Bin packing is infeasible")

    test_delay_calc(substrate_network, time_interval_count)

    run_some_tests(substrate_network)

    # TODO(Low prio): without config AMPL is not run...
    #
    # ampl_object = graph2ampl.get_complete_ampl_model_data('../ampl/system-model.mod',
    #                                                       service_instance, substrate_network,
    #                                                       {'time_interval_count': 12, 'coverage_threshold': 0.9, 'battery_threshold': 0.2})


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run_without_config_file()
    else:
        parser = argparse.ArgumentParser(description="Invokes volatile resources optimization task generation and "
                                                     "solves it with heuristic and AMPL formulation.")
        parser.add_argument('config', metavar='CONFIG_PATH', type=str)
        args = parser.parse_args()

        with open(args.config) as f:
            config = yaml.load(f.read())

            root_logger = logging.Logger('simulator')
            consol_handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
            file_handler = logging.FileHandler(config['simulator']['log_file'], 'w')
            formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
            consol_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(consol_handler)
            root_logger.addHandler(file_handler)
            root_logger.setLevel(config['simulator']['log_level'])

            root_logger.info("Generating infrastructure...")
            substrate_network = gs.InfrastructureGMLGraph(**config['infrastructure'], log=root_logger)
            root_logger.info("Generating service graph...")
            service_instance = gs.ServiceGMLGraph(substrate_network, **config['service'], log=root_logger)

            try:
                checker = cmf.VolatileResourcesChecker()
                mapper = cmf.ConstructiveMapperFromFractional(checker, log=root_logger)
                mapping_result_dict = mapper.map(substrate_network, service_instance)
            except Exception as e:
                root_logger.exception("Error during heuristic solution: ")
                # for development keep it raised
                raise

            try:
                root_logger.info("Creating AMPL solver support class...")
                # config['optimization'] is a python dictionary of optimization configuration parameters.
                export_data_if_needed = config['simulator']['export_ampl_data_path'] if "export_ampl_data_path" in config['simulator'] else None
                ampl_solver_support = AMPLSolverSupport(config['simulator']['ampl_model_path'], service_instance, substrate_network,
                                                        config['optimization'], log=root_logger,
                                                        export_ampl_data_path=export_data_if_needed)
                root_logger.info("Solving AMPL...")
                # ampl_solver_support.solve()
            except Exception as e:
                root_logger.exception("Error during AMPL solution: ")
                # for development keep raised
                raise
