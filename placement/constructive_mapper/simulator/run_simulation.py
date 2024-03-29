import sys
import argparse
import yaml
import os
import logging
import json
import traceback
import itertools
import multiprocessing as mp
import queue
import copy
from rainbow_logging_handler import RainbowLoggingHandler
sys.path.append(os.path.abspath(".."))

from ampl.ampl_support import AMPLSolverSupport
import graphs.generate_service as gs
from graphs.mapping_structure import VolatileResourcesMapping
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

            except cmf.UnfeasibleVolatileResourcesProblem:
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
    except cmf.UnfeasibleVolatileResourcesProblem:
        print("Bin packing is infeasible")

    test_delay_calc(substrate_network, time_interval_count)

    run_some_tests(substrate_network)

    # TODO(Low prio): without config AMPL is not run...
    #
    # ampl_object = graph2ampl.get_complete_ampl_model_data('../ampl/system-model.mod',
    #                                                       service_instance, substrate_network,
    #                                                       {'time_interval_count': 12, 'coverage_threshold': 0.9, 'battery_threshold': 0.2})


def run_with_config(config : dict, root_logger_name='simulator') -> tuple:
    """
    Executes the simulation with the given configuration.

    :param config:
    :return:
    """
    root_logger = logging.Logger(root_logger_name)
    consol_handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
    file_handler = logging.FileHandler(config['simulator']['log_file'], 'w')
    formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
    consol_handler.setFormatter(formatter)
    consol_handler.setLevel(config['simulator']['console_log_level'])
    file_handler.setFormatter(formatter)
    file_handler.setLevel(config['simulator']['file_log_level'])
    root_logger.addHandler(consol_handler)
    root_logger.addHandler(file_handler)
    # NOTE: Root loglevel is DEBUG so the handler level settings properly take effect
    root_logger.setLevel(logging.DEBUG)

    root_logger.info("Generating infrastructure...")
    substrate_network = gs.InfrastructureGMLGraph(**config['infrastructure'], log=root_logger)
    root_logger.info("Generating service graph...")
    service_instance = gs.ServiceGMLGraph(substrate_network, **config['service'], log=root_logger)

    algorithm_errors = list()
    heur_mapping_result_dict = None
    if config['simulator']['run_heuristic']:
        try:
            checker = cmf.VolatileResourcesChecker()
            mapper = cmf.ConstructiveMapperFromFractional(checker, log=root_logger, **config['optimization'])
            heur_mapping_result_dict = mapper.map(substrate_network, service_instance)
        except Exception as e:
            root_logger.exception("Error during heuristic solution: ")
            algorithm_errors.append(traceback.format_exc())

    ampl_mapping_result_dict = None
    if config['simulator']['run_ampl']:
        try:
            root_logger.info("Creating AMPL solver support class...")
            # config['optimization'] is a python dictionary of optimization configuration parameters.
            export_data_if_needed = config['simulator']['export_ampl_data_path'] if "export_ampl_data_path" in config['simulator'] else None
            ampl_solver_support = AMPLSolverSupport(config['simulator']['ampl_model_path'], service_instance, substrate_network,
                                                    config['optimization'], log=root_logger,
                                                    export_ampl_data_path=export_data_if_needed)
            root_logger.info("Solving AMPL...")
            ampl_mapping_result_dict = ampl_solver_support.solve()
        except Exception as e:
            root_logger.exception("Error during AMPL solution: ")
            algorithm_errors.append(traceback.format_exc())

    return heur_mapping_result_dict, ampl_mapping_result_dict, algorithm_errors


def setup_environment_for_single_execution(meta_config, simulation_id, current_config):
    """
    Creates a folder and log file for an execution

    :param meta_config:
    :param simulation_id:
    :param current_config:
    :return:
    """
    original_log_file_name = current_config['simulator']['log_file']
    simulation_name = meta_config['simulation_name']
    folder_path = "results/{}/{}".format(simulation_name, simulation_id)
    os.system("mkdir {}".format(folder_path))
    # set the current config to log to the newly created folder
    current_config['simulator']['log_file'] = "/".join((folder_path, original_log_file_name))
    # save the configuration file for this execution (so it is fully reproducible)
    with open("/".join((folder_path, "config.yml")), "w") as f:
        yaml.dump(current_config, f)
    # if the export path is given in the model, export the data to the testcase folder instead the original path.
    if "export_ampl_data_path" in current_config['simulator']:
        current_config['simulator']['export_ampl_data_path'] = "/".join((folder_path, "ampl_export.dat"))


def save_solution_for_single_execution(meta_config : dict, simulation_id : int, current_config : dict,
                                       heur_mapping : VolatileResourcesMapping, ampl_mapping : VolatileResourcesMapping):
    """
    Saves the solutions into json files

    :param meta_config:
    :param simulation_id:
    :param current_config:
    :return:
    """
    simulation_name = meta_config['simulation_name']
    folder_path = "results/{}/{}".format(simulation_name, simulation_id)
    if heur_mapping is not None:
        with open("/".join((folder_path, "heuristic_solution.json")), "w") as f:
            json.dump(heur_mapping, f, indent=4)
    if ampl_mapping is not None:
        with open("/".join((folder_path, "ampl_solution.json")), "w") as f:
            json.dump(ampl_mapping, f, indent=4)


def extract_simulations(meta_config : dict):
    """
    Extracts structures from the metaconfig to create all the simulations.

    :param meta_config:
    :return:
    """
    logger = logging.Logger('simulator')
    consol_handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
    logger.addHandler(consol_handler)
    formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
    consol_handler.setFormatter(formatter)
    simulation_name = meta_config['simulation_name']
    os.system("mkdir results/{}".format(simulation_name))
    file_handler = logging.FileHandler("results/{}/simulation.log".format(simulation_name), mode="w")
    logger.addHandler(file_handler)
    file_handler.setFormatter(formatter)
    base_config = meta_config['base_config_file']
    meta_config_values = meta_config['meta_config_values']
    with open(base_config) as f:
        base_config_dict = yaml.load(f.read())

        value_dict_for_zip = dict()
        if 'non_product_groups' in meta_config:
            non_product_groups = meta_config['non_product_groups']
            group_id = 0
            for group in non_product_groups:
                value_dict_for_zip[group_id] = []
                for item in group:
                    section, key = item.split(".")
                    value_dict_for_zip[group_id].append((section, key))
                group_id += 1
        value_lists_for_product = list()

        # collect the values to be used
        unpacked_non_products = dict()
        for section, section_values in meta_config_values.items():
            for key, value_list in section_values.items():
                for group_id, section_key_list in value_dict_for_zip.items():
                    if group_id not in unpacked_non_products:
                        unpacked_non_products[group_id] = []
                    # each section - key combination is only executed once
                    if (section, key) in section_key_list:
                        section_key_value_tuples = list()
                        for value in value_list:
                            section_key_value_tuples.append((section, key, value))
                            if section not in base_config_dict or key not in base_config_dict[section]:
                                raise Exception("Invalid meta config param, not found in base config: {}, {}".format(section, key))
                        unpacked_non_products[group_id].append(section_key_value_tuples)
                        break
                else:
                    # if the for cycle finishes (or is empty), aka this section, key is not in the values to be zipped.
                    values_of_single_key = []
                    for value in value_list:
                        values_of_single_key.append((section, key, value))
                        if section not in base_config_dict or key not in base_config_dict[section]:
                            raise Exception("Invalid meta config param, not found in base config: {}, {}".format(section, key))
                    value_lists_for_product.append(values_of_single_key)

        os.system("git show > results/{}/git-shows.txt".format(simulation_name))
        os.system("cd ../heuristic && git show >> ../simulator/results/{}/git-shows.txt && cd -".format(simulation_name))
        return logger, unpacked_non_products, value_lists_for_product, base_config_dict


def run_from_meta_config(meta_config : dict):
    """
    Creates single config files from a set of values

    :param meta_config:
    :return:
    """
    simulation_id = 0
    logger, unpacked_non_products, value_lists_for_product, current_config = extract_simulations(meta_config)

    if 'threads' in meta_config:
        max_parallel_processes = meta_config['threads']
    else:
        max_parallel_processes = 1
    current_active_processes = 0
    error_queue = mp.Queue()
    result_queue = mp.Queue()
    # instead of current_active_processes we could check the length of the Dict
    sim_id_to_process_dict = {}

    # zip the elements of all non product groups
    zipped_unpacked_non_products = {k: zip(*v) for k, v in unpacked_non_products.items()}

    for one_of_each_zipped_non_product_group in itertools.product(*list(zipped_unpacked_non_products.values())):
        sec_key_vals_to_set_at_once = []
        for tuple_to_flatten in one_of_each_zipped_non_product_group:
            sec_key_vals_to_set_at_once.extend(tuple_to_flatten)
        parallel_sim_config_str = ""
        # set the next values of each parallel parameters
        for section, key, value in sec_key_vals_to_set_at_once:
            current_config[section][key] = value
            parallel_sim_config_str += "{}.{}: {}; ".format(section, key, value)
        for values_one_of_each in itertools.product(*value_lists_for_product):
            product_sim_config_str = ""
            for psection, pkey, pvalue in values_one_of_each:
                current_config[psection][pkey] = pvalue
                product_sim_config_str += "{}.{}: {}; ".format(psection, pkey, pvalue)
            simulation_id += 1
            full_sim_config_str = product_sim_config_str + parallel_sim_config_str
            logger.info("=============================================================================================================")
            logger.info("Starting simulation \'{}\' with id: {}".format(meta_config['simulation_name'], simulation_id))
            logger.info("Current variable setting: {}".format(full_sim_config_str))
            # the config is modified by each thread
            sim_current_config = copy.deepcopy(current_config)
            # metaconfig should be read only, but lets still copy
            sim_meta_config = copy.deepcopy(meta_config)

            thread_args = sim_meta_config, simulation_id, sim_current_config, result_queue, error_queue
            add_more_processes_now = True
            if current_active_processes < max_parallel_processes:
                sim_id_to_process_dict[simulation_id] = mp.Process(target=setup_and_start_single_simulation,
                                                                   args=thread_args)
                sim_id_to_process_dict[simulation_id].start()
                current_active_processes +=1
                if current_active_processes == max_parallel_processes:
                    add_more_processes_now = False

            # TODO: might be refactored to other file, and would make sense to create a class...
            # if we have to wait, or we can launch the next process right away.
            if not add_more_processes_now:
                try:
                    unexpected_sim_error_trace = error_queue.get_nowait()
                    logger.error("Unexpected error during simulation, skipping to next simulation: {}".format(unexpected_sim_error_trace))
                except queue.Empty:
                    pass
                try:
                    # wait until there is any result, but at most some time, becuase if some error occured, we might never get result.
                    finished_simulation_id, heur_mapping, ampl_mapping, algorithm_errors = result_queue.get(True)
                    sim_id_to_process_dict[finished_simulation_id].join()
                    current_active_processes -= 1
                    logger.info("Joined process of simulation id {}".format(finished_simulation_id))
                    logger.debug("Mappings returned by heuristic: {}, AMPL: {}".format(heur_mapping, ampl_mapping))
                    for trace in algorithm_errors:
                        logger.error("Algorithm errors encountered: {}".format(trace))
                    # we do not need this process anymore
                    del sim_id_to_process_dict[finished_simulation_id]
                except queue.Empty:
                    logger.debug("No result, nor unexpected error found, the running processes are: {}".
                                 format(sim_id_to_process_dict))
                # in some cases (e.g. process was terminated by the OS due to memmory overusage) join() and error handling
                # are not enough...
                for sim_id, process in list(sim_id_to_process_dict.items()):
                    exitcode = sim_id_to_process_dict[sim_id].exitcode
                    if exitcode is not None:
                        if exitcode < 0:
                            logger.warning("Discarding terminated process of simulation id {} with exitcode {}".
                                            format(sim_id, exitcode))
                            current_active_processes -= 1
                            del sim_id_to_process_dict[sim_id]


def setup_and_start_single_simulation(meta_config, simulation_id, current_config, result_q : mp.Queue, error_q : mp.Queue):
    """
    Threadsafe function which creates and executes the algorithm instances with the given configs
    Creates environment and saves the result.

    :param meta_config:
    :param simulation_id:
    :param current_config:
    :param result_q:
    :param error_q:
    :return:
    """
    try:
        setup_environment_for_single_execution(meta_config, simulation_id, current_config)
        logger_name = "{}-{}".format(meta_config['simulation_name'], simulation_id)
        heur_mapping, ampl_mapping, algorithm_errors = run_with_config(current_config, root_logger_name=logger_name)
        save_solution_for_single_execution(meta_config, simulation_id, current_config, heur_mapping, ampl_mapping)
        result_q.put((simulation_id, heur_mapping, ampl_mapping, algorithm_errors))
    except Exception as e:
        error_q.put(traceback.format_exc())


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run_without_config_file()
    else:
        parser = argparse.ArgumentParser(description="Invokes volatile resources optimization task generation and "
                                                     "solves it with heuristic and AMPL formulation.")
        parser.add_argument('--single-config', type=str)
        parser.add_argument('--meta-config', type=str)
        args = parser.parse_args()
        if args.meta_config is not None and args.single_config is not None:
            raise Exception("meta config and single config cannot be given at the same time")

        if args.single_config is not None:
            with open(args.single_config) as f:
                single_config = yaml.load(f.read())
                heur_mapping_result_dict, ampl_mapping_result_dict, algorithm_errors = run_with_config(single_config)
                if heur_mapping_result_dict is not None:
                    print("HEURISTIC SOLUTION: " + json.dumps(heur_mapping_result_dict, indent=4))
                if ampl_mapping_result_dict is not None:
                    print("AMPL SOLUTION: " + json.dumps(ampl_mapping_result_dict, indent=4))
                print("ALGORITHM ERRORS: ")
                for trace in algorithm_errors:
                    print(trace)
        elif args.meta_config is not None:
            with open(args.meta_config) as f:
                meta_config = yaml.load(f.read())
                run_from_meta_config(meta_config)
        else:
            raise Exception("Either meta config or single config must be given.")


