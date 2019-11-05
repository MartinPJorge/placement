import json
import yaml
import os
import sys
sys.path.append(os.path.abspath(".."))
from graphs.mapping_structure import VolatileResourcesMapping


class DataExtractor(object):

    def __init__(self, config_file_name='config.yml', section_key_separator='.'):
        self.config_file_name = config_file_name
        self.sep = section_key_separator

    @staticmethod
    def get_objective_function_value(mapping : VolatileResourcesMapping, plot_data, plot_data_key):
        """
        Function which can be used as "plot_value_extractor" to extract objective function if the case is feasible

        :param mapping:
        :param plot_data:
        :param plot_data_key:
        :return:
        """
        if mapping[mapping.WORKED]:
            plot_data[plot_data_key].append(mapping[mapping.OBJECTIVE_VALUE])
        return plot_data

    def extract_plot_data(self, experiment_path, sim_id_num, sol_file_name : str, section_key_filters : dict,
                          dependent_section_key : str, section_keys_to_aggr : list, plot_value_extractor):
        """


        :param experiment_path:
        :param sim_id_num:
        :param section_key_filters:  example "simulator.run_ampl" = "True"
        :param dependent_section_key:
        :param section_keys_to_aggr:
        :param plot_value_extractor: Function to calculate the value to be plotted based on the mapping object
        :return:
        """
        plot_data = {}
        aggr_value_tuples = {}
        for sim_id in range(1, sim_id_num+1):
            sim_id_str = str(sim_id)
            with open("/".join((experiment_path, sim_id_str, self.config_file_name))) as config_f:
                config = yaml.load(config_f)
                skip_sim_id = False
                # skip the simulation ID if any of the filters are not met
                for k, value in section_key_filters.items():
                    section, key = k.split(self.sep)
                    if config[section][key] != value:
                        skip_sim_id = True
                        break
                if skip_sim_id:
                    continue

                # maintain error checking and plot data structures
                dep_sec, dep_key = dependent_section_key.split(self.sep)
                dependent_value = config[dep_sec][dep_key]
                if type(dependent_value) is list:
                    dependent_value = str(dependent_value)
                if dependent_value not in plot_data:
                    plot_data[dependent_value] = []
                    aggr_value_tuples[dependent_value] = list()

                # check if we are not adding some values twice!
                aggr_value_tup = list()
                for aggr_sec_key in section_keys_to_aggr:
                    agg_sec, agg_key = aggr_sec_key.split(self.sep)
                    aggr_value_tup.append(config[agg_sec][agg_key])
                aggr_value_tup = tuple(aggr_value_tup)
                if aggr_value_tup in aggr_value_tuples[dependent_value]:
                    raise Exception("Encoutnered the same aggregation value {} twice for dependent value {}".
                                    format(aggr_value_tup, dependent_value))
                else:
                    aggr_value_tuples[dependent_value].append(aggr_value_tup)

                # parse the solution
                with open("/".join((experiment_path, sim_id_str, sol_file_name))) as sol_f:
                    sol_dict = json.load(sol_f)
                    mapping = VolatileResourcesMapping(**sol_dict)
                    # extend the plotdata with the given method
                    plot_data = plot_value_extractor(mapping, plot_data, dependent_value)
        print(json.dumps(aggr_value_tuples, indent=2))
        return plot_data


if __name__ == "__main__":
    filter_dict = {"simulator.run_ampl": True,
                   "infrastructure.gml_file" : "../graphs/infras/cobo-calleja/pico-and-micro-cobo-calleja-ref-1.gml"}
    pd = DataExtractor().extract_plot_data("results/large_tests/", 480, sol_file_name="ampl_solution.json",
                                      section_key_filters=filter_dict,
                                      dependent_section_key="infrastructure.cluster_move_distances",
                                      section_keys_to_aggr=["service.seed"],
                                      plot_value_extractor=DataExtractor.get_objective_function_value)

    # filter_dict = {"simulator.run_heuristic": True,
    #                "infrastructure.unloaded_battery_alive_prob" : 0.99}
    # pd = DataExtractor().extract_plot_data("results/tests/", 27, sol_file_name="heuristic_solution.json",
    #                                   section_key_filters=filter_dict,
    #                                   dependent_section_key="optimization.improvement_score_limit",
    #                                   section_keys_to_aggr=["infrastructure.gml_file"],
    #                                   plot_value_extractor=DataExtractor.get_objective_function_value)
    print("AMPL\n", json.dumps(pd, indent=2))

    filter_dict = {"simulator.run_ampl": True,
                   "infrastructure.gml_file": "../graphs/infras/cobo-calleja/pico-and-micro-cobo-calleja-ref-1.gml"}
    pd = DataExtractor().extract_plot_data("results/large_tests/", 480, sol_file_name="heuristic_solution.json",
                                           section_key_filters=filter_dict,
                                           dependent_section_key="infrastructure.cluster_move_distances",
                                           section_keys_to_aggr=["service.seed"],
                                           plot_value_extractor=DataExtractor.get_objective_function_value)
    print("HEUR\n", json.dumps(pd, indent=2))
