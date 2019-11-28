import json
import yaml
import os
import sys
import logging
import numpy as np
from rainbow_logging_handler import RainbowLoggingHandler
import matplotlib.pyplot as plt
import matplotlib.lines as lines
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
    "service.connected_component_sizes" : "Number of NFs",
    "service.sfc_delays": "Delays of SFCs [ms]",
    "optimization.battery_threshold": "Battery alive probabilty",
    "service.mobile_nfs_per_sfc": "NF count bound to mobile nodes",
    "optimization.coverage_threshold": "Coverage probability"
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

    @staticmethod
    def count_handovers(mapping: VolatileResourcesMapping, plot_data, plot_data_key):
        if mapping[mapping.WORKED]:
            previous_ap_name = None
            # the first difference is not a handover
            handover_count = -1
            # must be sorted based on subinterval (not guaranteed in dicts)
            sorted_ap_sel = list(mapping[mapping.AP_SELECTION].items())
            sorted_ap_sel = sorted(sorted_ap_sel, key=lambda t: int(t[0]))
            for subinterval, ap_name in sorted_ap_sel:
                if ap_name != previous_ap_name:
                    handover_count += 1
                    previous_ap_name = ap_name
            plot_data[plot_data_key].append(handover_count)
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

    def __init__(self, data_extractor : DataExtractor = None, output_filetype='png', plots_path=None):
        if data_extractor is not None:
            self.data_extractor = data_extractor
            self.plots_path = os.path.join(data_extractor.experiment_path, "plots")
            os.system("mkdir {}".format(self.plots_path))
        elif plots_path is not None:
            self.plots_path = plots_path
        else:
            raise ValueError("Data extractor object or plots path must be specified!")
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

        full_file_name = os.path.join(self.plots_path, file_name) + self.output_filetype
        log.info("Saving plot {}...".format(full_file_name))
        plt.savefig(full_file_name)
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
            x_labels.append(str(key))
        ax.bar(x_labels, bar_heights)

        ax.set_xlabel(config_section_key_to_axis_label_dict[dependent_section_key])
        ax.set_ylabel(y_axis_label)

        full_file_name = os.path.join(self.plots_path, file_name) + self.output_filetype
        log.info("Saving plot {}...".format(full_file_name))
        plt.savefig(full_file_name)
        plt.close(fig)


class MakeCompareBoxPlot(MakeBoxPlot):

    def __init__(self, data_extractor : DataExtractor = None, output_filetype='png', plots_path=None,
                 show_feasibility_percentage=False, max_sample_size=1):
        super(MakeCompareBoxPlot, self).__init__(data_extractor, output_filetype, plots_path)
        self.show_feasibility_percentage = show_feasibility_percentage
        self.max_sample_size = max_sample_size
        self.linestyle_list = [
            {'linewidth': 1, 'color': 'black', 'linestyle': '-'},
            {'linewidth': 1, 'color': 'red', 'linestyle': '--'},
            {'linewidth': 1, 'color': 'green', 'linestyle': '-.'},
            {'linewidth': 1, 'color': 'blue', 'linestyle': ':'}
        ]
        self.flierstyle_list = [
            {'markeredgecolor': 'black'},
            {'markeredgecolor': 'red'},
            {'markeredgecolor': 'green'},
            {'markeredgecolor': 'blue'},
        ]

    def make_and_save_plot(self, file_name, dict_of_plot_data, dependent_section_key, y_axis_label):
        """


        :param file_name:
        :param dict_of_plot_data: keys are legend items, values are dict of plot_data in the same struct as in baseclass
        :param dependent_section_key:
        :param y_axis_label:
        :return:
        """
        if len(dict_of_plot_data) == 0:
            return
        fig, ax = plt.subplots()
        legend_from_keys = []
        dependent_data_lables = None
        for k, k_plot_data in dict_of_plot_data.items():
            legend_from_keys.append(k)
            if dependent_data_lables is None:
                dependent_data_lables = list(k_plot_data.keys())
            elif dependent_data_lables != list(k_plot_data.keys()):
                raise Exception("Data labels of each plot_data must be the same, in same order! but {} and {} is wrong".
                                format(dependent_data_lables, list(k_plot_data.keys())))
        # skip the box spaces which we added to separate the values
        pos_offset = 1
        boxes_artists = []
        for legend_name in legend_from_keys:
            # take one data from each dataset, which corresponds to the same value
            values_to_plot = []
            for x_label in dependent_data_lables:
                values_to_plot.append(dict_of_plot_data[legend_name][x_label])
            pos = [i * (len(legend_from_keys)+1) + pos_offset for i in range(0, len(dependent_data_lables))]
            boxplot_res = ax.boxplot(values_to_plot, positions=pos, whis=1.5,
                       boxprops=self.linestyle_list[pos_offset-1], medianprops=self.linestyle_list[pos_offset-1],
                       whiskerprops=self.linestyle_list[pos_offset-1], flierprops=self.flierstyle_list[pos_offset-1],
                       capprops=self.linestyle_list[pos_offset-1])
            pos_offset += 1
            boxes_artists.append(boxplot_res["boxes"][0])
        xtick_offset = len(legend_from_keys)/2+0.5 if len(legend_from_keys)%2==0 else len(legend_from_keys)//2+1
        xtick_positions = [xtick_offset + (len(legend_from_keys)+1)*i for i in range(0, len(dependent_data_lables))]
        # in some cases these are lists, should show them without brackets
        dependent_data_lables_removed_brackets = map(lambda l: l.rstrip("]").lstrip("["), dependent_data_lables)
        plt.xticks(xtick_positions, dependent_data_lables_removed_brackets)
        # reverse both so they would match the order of the feasibilty numbers
        ax.legend(reversed(boxes_artists), reversed(legend_from_keys), loc='upper left')

        ax.set_xlabel(config_section_key_to_axis_label_dict[dependent_section_key])
        ax.set_ylabel(y_axis_label)

        # show_feasibility_percentage on top of each group
        if self.show_feasibility_percentage:
            # ax.text(-0.6, 1.05, "Scenario\nfeasibility", transform=ax.get_xaxis_transform(), fontsize=10)
            legend_idx = 0
            ax.text(-1.9, 1.01+0.04*(len(legend_from_keys)-1)/2.0, "Feasib.", transform=ax.get_xaxis_transform(),
                    horizontalalignment='center', fontsize=10)
            for legend_name in legend_from_keys:
                y_coord = 1.01+0.04*legend_idx
                legendline = lines.Line2D([-0.4, 0.7], [y_coord+0.02, y_coord+0.02],
                                          **self.linestyle_list[legend_idx], transform=ax.get_xaxis_transform(), figure=fig)
                fig.lines.extend([legendline])
                for xtick, data_label in zip(xtick_positions, dependent_data_lables):
                    feasibility = len(dict_of_plot_data[legend_name][data_label]) / self.max_sample_size
                    ax.text(xtick, y_coord, str(int(np.round(feasibility * 100)))+'%', transform=ax.get_xaxis_transform(),
                            horizontalalignment='center')
                legend_idx += 1

        full_file_name = os.path.join(self.plots_path, file_name) + self.output_filetype
        log.info("Saving plot {}...".format(full_file_name))
        plt.savefig(full_file_name)
        plt.close(fig)



def plot_both_if_needed(de : DataExtractor, plotter : MakeBoxPlot, plot_value_func, dependent_section_key,
                        name, improvement_limit, ampl_improvement_limit=2, additional_filters=None, additional_aggr=None):
    section_key_filters = {"optimization.improvement_score_limit": improvement_limit}
    aggregation_keys = ["service.seed"]
    if additional_filters is not None:
        section_key_filters.update(additional_filters)
    if additional_aggr is not None:
        aggregation_keys.extend(additional_aggr)
    if improvement_limit == ampl_improvement_limit:
        pd1 = de.extract_plot_data(sol_file_name="ampl_solution.json",
                                   section_key_filters=section_key_filters,
                                   dependent_section_key=dependent_section_key,
                                   section_keys_to_aggr=aggregation_keys,
                                   plot_value_extractor=plot_value_func)
        plotter.make_and_save_plot("ampl-{}".format(name), pd1, dependent_section_key, name)
    pd1 = de.extract_plot_data(sol_file_name="heuristic_solution.json",
                               section_key_filters=section_key_filters,
                               dependent_section_key=dependent_section_key,
                               section_keys_to_aggr=aggregation_keys,
                               plot_value_extractor=plot_value_func)
    plotter.make_and_save_plot("heuristic-{}-impr-{}".format(name, improvement_limit), pd1, dependent_section_key, name)


help_text = "Positional arguments are either \n" \
            "(1) a simulation name (name of folder) without any other,\n" \
            "(2) (a) .json file in local_replot_data folder, \n" \
            "\t (b) dependent_section_key (e.g. optimization.coverage_threshold)\n" \
            "\t (c) max_sample_size giving the divisor in the feasibility ratio, calculated from the sample size (if 1 then skip plotting feasibilty)" \
            "\t (d) y_axis_label is the label to be shown on y axes"

if __name__ == "__main__":

    if len(sys.argv) > 1:
        simulation_name = sys.argv[1]
    else:
        simulation_name = ""
    if "-h" in sys.argv or "--help" in sys.argv:
        print(help_text)
    elif ".json" in simulation_name:
        # replot from file, the chosen data
        replot_file = simulation_name
        try:
            dependent_section_key = sys.argv[2]
            max_sample_size = int(sys.argv[3])
            y_axis_label = sys.argv[4]
        except:
            print(help_text)
            raise ValueError("Missing input parameters!")
        replot_file_path = os.path.join('local_replot_data', replot_file)
        with open(replot_file_path, "r") as f:
            replot_data = json.load(f)
            # in this case we would use non comparing plots... could be refactored to make nicer...
            # plotter = MakeFeasibilityPlot(output_filetype='png', plots_path='local_replot_data')
            plotter = MakeCompareBoxPlot(output_filetype='png', plots_path='local_replot_data',
                                         max_sample_size=max_sample_size, show_feasibility_percentage=max_sample_size != 1)
            plotter.make_and_save_plot(replot_file.rstrip(".json"), replot_data, dependent_section_key, y_axis_label)
    elif simulation_name == "large_tests_many_nfs":
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
    elif simulation_name == "mobile_nf_loads_targeted":
        de = DataExtractor("results/mobile_nf_loads_targeted", 224)
        for plotter, plot_value_func, name in ((MakeBoxPlot(de, "png"), DataExtractor.get_objective_function_value, 'cost'),
                                               (MakeBoxPlot(de, "png"), DataExtractor.get_running_time, "runtime")):
            for improvement_limit in (2, 1):
                log.debug("Plotting: {}, with improvement limit {}".format(name, improvement_limit))
                plot_both_if_needed(de, plotter, plot_value_func, "service.mobile_nfs_per_sfc", name, improvement_limit)
    elif simulation_name == "scalability_test":
        de = DataExtractor("results/scalability_test", 336)
        for plotter, plot_value_func, name in ((MakeBoxPlot(de, "png"), DataExtractor.get_objective_function_value, 'cost'),
                                               (MakeBoxPlot(de, "png"), DataExtractor.get_running_time, "runtime")):
            for improvement_limit in (2, 1):
                log.debug("Plotting: {}, with improvement limit {}".format(name, improvement_limit))
                plot_both_if_needed(de, plotter, plot_value_func, "service.connected_component_sizes", name, improvement_limit)
    elif simulation_name == "mobile_nf_loads_small_sweep":
        de = DataExtractor("results/mobile_nf_loads_small_sweep", 1344)
        for plotter, plot_value_func, name in ((MakeBoxPlot(de, "png"), DataExtractor.get_objective_function_value, 'cost'),
                                               (MakeBoxPlot(de, "png"), DataExtractor.get_running_time, "runtime"),
                                               (MakeFeasibilityPlot(de, "png"), DataExtractor.count_feasible, 'feas')):
            for battery_threshold in [0.656, 0.6872, 0.7184, 0.7496, 0.7808, 0.812]:
                additional_filters = {"optimization.battery_threshold": battery_threshold}
                for improvement_limit in (2, 1):
                    log.debug("Plotting: {}, with improvement limit {}, battery threashold {}".format(name, improvement_limit, battery_threshold))
                    try:
                        plot_both_if_needed(de, plotter, plot_value_func, "service.mobile_nfs_per_sfc", name + "-battery_th-{}".format(battery_threshold),
                                            improvement_limit, additional_filters=additional_filters)
                    except Exception as e:
                        log.exception("Error during plotting, skipping plot...")
    elif simulation_name == "coverage_threshold_variation":
        de = DataExtractor("results/coverage_threshold_variation", 576)
        for plotter, plot_value_func, name in ((MakeBoxPlot(de, "png"), DataExtractor.get_objective_function_value, 'cost'),
                                               (MakeBoxPlot(de, "png"), DataExtractor.get_running_time, "runtime"),
                                               (MakeFeasibilityPlot(de, "png"), DataExtractor.count_feasible, 'feas'),
                                               (MakeBoxPlot(de, "png"), DataExtractor.count_handovers, "handovers")):
            for improvement_limit in (2, 1, 0):
                try:
                    plot_both_if_needed(de, plotter, plot_value_func, "optimization.coverage_threshold", name, improvement_limit,
                                        additional_aggr=["infrastructure.gml_file"])
                    for haven_id in (1, 2, 3, 4):
                        plot_both_if_needed(de, plotter, plot_value_func, "optimization.coverage_threshold", name+"-haven-{}".format(haven_id),
                                            improvement_limit,
                                            additional_filters={"infrastructure.gml_file": "../graphs/infras/valencia-haven/valencia-haven-{}.gml".format(haven_id)})
                except Exception as e:
                    log.exception("Error during plotting, skipping plot...")
    elif simulation_name == "e2e_delay_effect":
        de = DataExtractor("results/e2e_delay_effect", 1200)
        for plotter, plot_value_func, name in ((MakeBoxPlot(de, "png"), DataExtractor.get_objective_function_value, 'cost'),
                                               (MakeBoxPlot(de, "png"), DataExtractor.get_running_time, "runtime"),
                                               (MakeBoxPlot(de, "png"), DataExtractor.count_handovers, "handovers")):
            for sfcs in [[10], [10, 10], [10, 10, 10]]:
                for improvement_limit in (3, 2, 1, 0):
                    try:
                        plot_both_if_needed(de, plotter, plot_value_func, "service.sfc_delays", name + "-sfcs-{}".format(len(sfcs)), improvement_limit,
                                            additional_aggr=["infrastructure.gml_file"],
                                            additional_filters={"service.connected_component_sizes": sfcs},
                                            ampl_improvement_limit=3)
                    except Exception as e:
                        log.exception("Error during plotting, skipping plot...")
    else:
        raise ValueError("Unknown simulation name {}".format(simulation_name))
