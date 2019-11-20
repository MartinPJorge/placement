import json
import yaml
import os
import sys
import logging
import numpy as np
from rainbow_logging_handler import RainbowLoggingHandler
import matplotlib.pyplot as plt
sys.path.append(os.path.abspath(".."))
from graphs.mapping_structure import VolatileResourcesMapping


log = logging.getLogger("Plotter")
consol_handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
consol_handler.setFormatter(formatter)
consol_handler.setLevel("DEBUG")
file_handler = logging.FileHandler("results/plotting.log", 'w')
file_handler.setFormatter(formatter)
file_handler.setLevel("DEBUG")
log.addHandler(consol_handler)
log.addHandler(file_handler)
log.setLevel("DEBUG")


config_section_key_to_axis_label_dict = {
    "infrastructure.cluster_move_distances": "Cluster move length [Lat,Lon dist.]",
    "service.connected_component_sizes" : "Connected component sizes in request",
    "service.sfc_delays": "Delays of SFCs [ms]",
    "optimization.battery_threshold": "Battery alive probabilty",
    "service.mobile_nfs_per_sfc": "NF count bound to mobile nodes"
}


class DataExtractor(object):

    def __init__(self,  experiment_path, sim_id_num, config_file_name='config.yml', section_key_separator='.'):
        self.experiment_path = experiment_path
        self.sim_id_num = sim_id_num
        self.config_file_name = config_file_name
        self.sep = section_key_separator

    @staticmethod
    def get_running_time(mapping : VolatileResourcesMapping, plot_data, plot_data_key):
        if mapping[mapping.RUNNING_TIME] is not None:
            plot_data[plot_data_key].append(mapping[mapping.RUNNING_TIME])
        return plot_data

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

    @staticmethod
    def count_feasible(mapping: VolatileResourcesMapping, plot_data, plot_data_key):
        """

        :param mapping:
        :param plot_data:
        :param plot_data_key:
        :return:
        """
        if mapping[mapping.WORKED]:
            plot_data[plot_data_key].append(1)
        else:
            plot_data[plot_data_key].append(0)
        return plot_data

    def extract_plot_data(self, sol_file_name : str, section_key_filters : dict,
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
        log.info("Extracting plot data based on params: \ndependent_section_key: {}\nsection_keys_to_aggr: {}\nsection_key_filters: {}".
                 format(dependent_section_key, section_keys_to_aggr, section_key_filters))
        plot_data = {}
        aggr_value_tuples = {}
        for sim_id in range(1, self.sim_id_num+1):
            sim_id_str = str(sim_id)
            with open("/".join((self.experiment_path, sim_id_str, self.config_file_name))) as config_f:
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
                    raise Exception("Encountered the same aggregation value {} twice for dependent value {}".
                                    format(aggr_value_tup, dependent_value))
                else:
                    aggr_value_tuples[dependent_value].append(aggr_value_tup)

                # parse the solution
                try:
                    sol_path = "/".join((self.experiment_path, sim_id_str, sol_file_name))
                    with open(sol_path) as sol_f:
                        sol_dict = json.load(sol_f)
                        mapping = VolatileResourcesMapping(**sol_dict)
                        log.debug("Mapping object of simulation id {}:\n{}".format(sim_id_str, mapping))
                        # extend the plotdata with the given method
                        plot_data = plot_value_extractor(mapping, plot_data, dependent_value)
                except FileNotFoundError as e:
                    log.error("File not found {} Skipping plot creation".format(sol_path))
        if len(aggr_value_tuples) == 0 or len(plot_data) == 0:
            log.warn("Skipped simulation id {} due to {} != {} for section: {} key: {}".
                      format(sim_id, config[section][key], value, section, key))
        log.debug("Aggregation value tuples: \n{}".format(json.dumps(aggr_value_tuples, indent=2)))
        log.info("Data to be plotted: \n{}".format(json.dumps(plot_data, indent=2)))
        return plot_data


class MakeBoxPlot(object):

    def __init__(self, data_extractor: DataExtractor, output_filetype):
        self.data_extractor = data_extractor
        self.plots_path = os.path.join(data_extractor.experiment_path, "plots")
        os.system("mkdir {}".format(self.plots_path))
        self.output_filetype = "." + output_filetype

    def make_and_save_plot(self, file_name, plot_data, dependent_section_key, y_axis_label):
        """
        Creates boxplot, where the body of the box are the 1st to 3rd quartile of the data, whiskers are a
        multiplier of the interquartile range Q3-Q1.

        :param plot_data:
        :param y_axis_label:
        :return:
        """
        if len(plot_data) == 0:
            return
        fig, ax = plt.subplots()
        pos = np.array(range(len(plot_data))) + 1
        values_to_plot = []
        for k in plot_data.keys():
            values_to_plot.append(plot_data[k])
        ax.boxplot(values_to_plot, positions=pos, whis=1.5,
                   boxprops={'linewidth': 2}, medianprops={'linewidth': 3}, whiskerprops={'linewidth': 1.8})
        ax.set_xticklabels(plot_data.keys())
        ax.set_xlabel(config_section_key_to_axis_label_dict[dependent_section_key])
        ax.set_ylabel(y_axis_label)

        # show sample size
        ax.text(0.0, 1.05, "sample size", transform=ax.get_xaxis_transform())
        for xtick, data_label in zip(pos, plot_data.keys()):
            ax.text(xtick, 1.05, str(len(plot_data[data_label])), transform=ax.get_xaxis_transform())

        plt.savefig(os.path.join(self.plots_path, file_name) + self.output_filetype)
        plt.close(fig)


class MakeFeasibilityPlot(MakeBoxPlot):

    def make_and_save_plot(self, file_name, plot_data, dependent_section_key, y_axis_label='Feasibilty [%]'):
        """
        Plots data to be 1s and 0s to indicate the feasibilty of the scenarios, plots boxes up to the ratio of feasible scenarios.

        :param file_name:
        :param plot_data:
        :param dependent_section_key:
        :param y_axis_label:
        :return:
        """
        if len(plot_data) == 0:
            return
        fig, ax = plt.subplots()
        bar_heights = []
        x_labels = []
        for key, values in plot_data.items():
            bar_heights.append(np.round(sum(values)/len(values) * 100.0, decimals=2))
            x_labels.append(key)
        ax.bar(x_labels, bar_heights)

        ax.set_xlabel(config_section_key_to_axis_label_dict[dependent_section_key])
        ax.set_ylabel(y_axis_label)

        plt.savefig(os.path.join(self.plots_path, file_name) + self.output_filetype)
        plt.close(fig)


if __name__ == "__main__":

    if len(sys.argv) > 1:
        simulation_name = sys.argv[1]
    else:
        simulation_name = ""
    if simulation_name == "large_tests_many_nfs":
        ref_to_path = {
            'ref-1': "../graphs/infras/cobo-calleja/pico-and-micro-cobo-calleja-ref-1.gml",
            'ref-2': "../graphs/infras/cobo-calleja/pico-and-micro-cobo-calleja-ref-2.gml",
            'ref-3': "../graphs/infras/cobo-calleja/pico-and-micro-cobo-calleja-ref-3.gml"
        }
        de = DataExtractor("results/large_tests_many_nfs", 196)
        boxplotter = MakeBoxPlot(de, "png")
        for plot_value_func, name in ((DataExtractor.get_objective_function_value, "cost"), (DataExtractor.get_running_time, "runtime")):
            for ref in ('ref-1', 'ref-2', 'ref-3'):
                for improvement_limit in (3, 2, 1, 4):
                    filter_dict = {"optimization.improvement_score_limit": improvement_limit,
                                   "infrastructure.gml_file" : ref_to_path[ref]}
                    if improvement_limit == 3:
                        # this was the only non product group element, when the AMPL was run
                        pd1 = de.extract_plot_data(sol_file_name="ampl_solution.json",
                                                   section_key_filters=filter_dict,
                                                   dependent_section_key="infrastructure.cluster_move_distances",
                                                   section_keys_to_aggr=["service.seed"],
                                                   plot_value_extractor=plot_value_func)
                        boxplotter.make_and_save_plot("ampl-{}-on-{}".format(name, ref), pd1, "infrastructure.cluster_move_distances", name)

                    pd2 = de.extract_plot_data(sol_file_name="heuristic_solution.json",
                                               section_key_filters=filter_dict,
                                               dependent_section_key="infrastructure.cluster_move_distances",
                                               section_keys_to_aggr=["service.seed"],
                                               plot_value_extractor=plot_value_func)
                    boxplotter.make_and_save_plot("heuristic-{}-on-{}-impr-{}".format(name, ref, improvement_limit), pd2, "infrastructure.cluster_move_distances", name)
    elif simulation_name == "feasibility_sweep_fixed_improved_timelim":
        de = DataExtractor("results/feasibility_sweep_fixed_improved_timelim", 384)
        boxplotter = MakeBoxPlot(de, "png")
        for fixed_param_name, dependent_param_name, values in (('connected_component_sizes', 'sfc_delays', ([10], [10, 10, 10], [20, 20, 20])),
                                                               ('sfc_delays', 'connected_component_sizes', ([5, 5, 5], [10, 10, 10], [15, 15, 15], [1000, 1000, 1000]))):
            for fix_param_v in values:
                for plot_value_func, name in ((DataExtractor.get_objective_function_value, "cost"), (DataExtractor.get_running_time, "runtime")):
                    for improvement_limit in (4, 3, 2, 1):
                        log.debug("Params to be plotted: {}, {}".format(fixed_param_name, fix_param_v, name, improvement_limit))
                        if improvement_limit == 4:
                            # this was the only non product group element, when the AMPL was run
                            pd1 = de.extract_plot_data(sol_file_name="ampl_solution.json",
                                                       section_key_filters={"service."+fixed_param_name: fix_param_v,
                                                                            "optimization.improvement_score_limit": improvement_limit},
                                                       dependent_section_key="service."+dependent_param_name,
                                                       section_keys_to_aggr=["service.seed", "infrastructure.gml_file"],
                                                       plot_value_extractor=plot_value_func)
                            boxplotter.make_and_save_plot("ampl-{}-{}-{}".format(name, fixed_param_name, fix_param_v), pd1, "service." + dependent_param_name, name)
                        #
                        pd2 = de.extract_plot_data(sol_file_name="heuristic_solution.json",
                                                   section_key_filters={"service."+fixed_param_name: fix_param_v,
                                                                        "optimization.improvement_score_limit": improvement_limit},
                                                   dependent_section_key="service." + dependent_param_name,
                                                   section_keys_to_aggr=["service.seed", "infrastructure.gml_file"],
                                                   plot_value_extractor=plot_value_func)
                        boxplotter.make_and_save_plot("heuristic-{}-{}-{}-impr-{}".format(name, fixed_param_name, fix_param_v, improvement_limit),
                                                      pd2, "service." + dependent_param_name, name)
    elif simulation_name == "FEASPLOTS_feasibility_sweep_fixed_improved_timelim":
        de = DataExtractor("results/feasibility_sweep_fixed_improved_timelim", 384)
        barplotter = MakeFeasibilityPlot(de, "png")
        for fixed_param_name, dependent_param_name, values in (('connected_component_sizes', 'sfc_delays', ([10], [10, 10, 10], [20, 20, 20])),):
            for fix_param_v in values:
                plot_value_func = DataExtractor.count_feasible
                name = 'feasibility'
                for improvement_limit in (4, 3, 2, 1):
                    log.debug("Params to be plotted: {}, {}".format(fixed_param_name, fix_param_v, name, improvement_limit))
                    if improvement_limit == 4:
                        # this was the only non product group element, when the AMPL was run
                        pd1 = de.extract_plot_data(sol_file_name="ampl_solution.json",
                                                   section_key_filters={"service." + fixed_param_name: fix_param_v,
                                                                        "optimization.improvement_score_limit": improvement_limit},
                                                   dependent_section_key="service." + dependent_param_name,
                                                   section_keys_to_aggr=["service.seed", "infrastructure.gml_file"],
                                                   plot_value_extractor=plot_value_func)
                        barplotter.make_and_save_plot("ampl-{}-{}-{}".format(name, fixed_param_name, fix_param_v), pd1, "service." + dependent_param_name)
                    #
                    pd2 = de.extract_plot_data(sol_file_name="heuristic_solution.json",
                                               section_key_filters={"service." + fixed_param_name: fix_param_v,
                                                                    "optimization.improvement_score_limit": improvement_limit},
                                               dependent_section_key="service." + dependent_param_name,
                                               section_keys_to_aggr=["service.seed", "infrastructure.gml_file"],
                                               plot_value_extractor=plot_value_func)
                    barplotter.make_and_save_plot("heuristic-{}-{}-{}-impr-{}".format(name, fixed_param_name, fix_param_v, improvement_limit),
                                                  pd2, "service." + dependent_param_name)
    elif simulation_name == "mobile_nf_loads":
        de = DataExtractor("results/mobile_nf_loads", 450)
        # running time might not be interesting at all in this test
        for plotter, plot_value_func, name, y_axis_label in ((MakeFeasibilityPlot(de, "png"), DataExtractor.count_feasible, 'feas', 'Feasibilty [%]'),
                                                             (MakeBoxPlot(de, "png"), DataExtractor.get_objective_function_value, 'cost', 'Cost of embedding')):
            for fixed_param_name, dependent_param_name, values in (("service.mobile_nfs_per_sfc", "optimization.battery_threshold", [0, 4, 8, 12, 16, 18]),
                                                                   ("optimization.battery_threshold", "service.mobile_nfs_per_sfc", [0.4, 0.5623, 0.6248, 0.8123, 0.9373])):
                for fix_param_v in values:
                    for improvement_limit in (3, 2, 1):
                        log.debug("Params to be plotted: {}, {}".format(fixed_param_name, fix_param_v, name, improvement_limit))
                        if improvement_limit == 3:
                            pd1 = de.extract_plot_data(sol_file_name="ampl_solution.json",
                                                       section_key_filters={fixed_param_name: fix_param_v,
                                                                            "optimization.improvement_score_limit": improvement_limit},
                                                       dependent_section_key=dependent_param_name,
                                                       section_keys_to_aggr=["service.seed"],
                                                       plot_value_extractor=plot_value_func)
                            plotter.make_and_save_plot("ampl-{}-{}-{}".format(name, fixed_param_name, fix_param_v), pd1, dependent_param_name, y_axis_label)
                        # for each improvement score limit
                        pd2 = de.extract_plot_data(sol_file_name="heuristic_solution.json",
                                                   section_key_filters={fixed_param_name: fix_param_v,
                                                                        "optimization.improvement_score_limit": improvement_limit},
                                                   dependent_section_key=dependent_param_name,
                                                   section_keys_to_aggr=["service.seed"],
                                                   plot_value_extractor=plot_value_func)
                        plotter.make_and_save_plot("heuristic-{}-{}-{}-impr-{}".format(name, fixed_param_name, fix_param_v, improvement_limit), pd2, dependent_param_name, y_axis_label)
    else:
        raise ValueError("Unknown simulation name {}".format(simulation_name))
