import logging
import sys
from rainbow_logging_handler import RainbowLoggingHandler
import traceback
import time

import amplpy

from graphs.generate_service import InfrastructureGMLGraph, ServiceGMLGraph
from graphs.mapping_structure import VolatileResourcesMapping
from ampl.graph2ampl import get_complete_ampl_model_data


class AMPLErrorHandler(amplpy.ErrorHandler):

    def __init__(self, log):
        self.log = log

    def error(self, amplexception):
        """
        Receives notification of an error.
        """
        msg = '\n\t'+str(amplexception).replace('\n', '\n\t')
        self.log.error(msg)
        # NOTE: AMPL's
        raise amplexception

    def warning(self, amplexception):
        """
        Receives notification of a warning.
        """
        msg = '\n\t'+str(amplexception).replace('\n', '\n\t')
        self.log.warn(msg)


class AMPLSolverSupport(object):

    def __init__(self, ampl_model_path, service_instance : ServiceGMLGraph, substrate_network : InfrastructureGMLGraph,
                 optimization_kwargs : dict, log = None, export_ampl_data_path=None):
        """
        Facilitates communicating with the AMPL object so it it easy to call the AMPL solution from the simulator.
        Raises an Exception baseclass if something occours which MUST be corrected, or MUSTNOT happen.

        :param ampl_model_path:
        :param service_instance:
        :param substrate_network:
        :param optimization_kwargs:
        :param log:
        :param export_ampl_data_path: saves the data in a .dat file if it is given
        """
        if log is None:
            self.log = logging.Logger(self.__class__.__name__)
            handler = RainbowLoggingHandler(sys.stderr, color_funcName=('black', 'yellow', True))
            formatter = logging.Formatter('%(asctime)s.%(name)s.%(levelname).3s: %(message)s')
            handler.setFormatter(formatter)
            self.log.addHandler(handler)
            self.log.setLevel(logging.DEBUG)
        else:
            self.log = log.getChild(self.__class__.__name__)
            for handler in log.handlers:
                self.log.addHandler(handler)
            self.log.setLevel(log.getEffectiveLevel())

        self.log.info("Parsing optimization task into AMPL data structure...")
        # AMPL object provided by the library
        self.ampl = get_complete_ampl_model_data(ampl_model_path, service_instance, substrate_network, optimization_kwargs, log = log)
        self.optimization_kwargs = optimization_kwargs
        self.service_instance = service_instance
        self.substrate_network = substrate_network
        self.ampl.setErrorHandler(AMPLErrorHandler(self.log))
        if export_ampl_data_path is not None:
            # NOTE: Full zero rows/columns are not shown anywhere in the .dat file???
            self.log.info("Saving the generated AMPL data to file path {}".format(export_ampl_data_path))
            self.ampl.exportData(export_ampl_data_path)
        self.log.info("Parsing to AMPL is successful!")
        self.ampl.setOption('solver', 'gurobi')
        self.ampl.eval('option gurobi_options \'mipgap 0.9 timelim 1800 threads 1\';')
        self.start_timestamp = None

    def construct_mapping(self, objective : amplpy.objective.Objective):
        """
        Constructs a VolatileResourcesMapping object according to the solver's results.

        :param objective:
        :return:
        """
        mapping = VolatileResourcesMapping()
        try:
            result_str = objective.result()
        except RuntimeError as e:
            return mapping
        if result_str == 'infeasible':
            mapping[mapping.RUNNING_TIME] = time.time() - self.start_timestamp
            return mapping
        elif result_str == 'solved':
            mapping[VolatileResourcesMapping.WORKED] = True
            for var_name, var in self.ampl.getVariables():
                # node mapping decision variables
                if var_name == 'X':
                    for key, value in var.getValues().toDict().items():
                        # it is a binary in float, so safe to compare
                        if value == 1.0:
                            nf_name, infra_name = key
                            mapping[nf_name] = infra_name
                elif var_name == 'AP_x':
                    for key, value in var.getValues().toDict().items():
                        if value == 1.0:
                            ap_name, subinterval = key
                            mapping.add_access_point_selection(subinterval, ap_name)

            if not mapping.validate_mapping(self.service_instance, self.substrate_network, **self.optimization_kwargs):
                raise Exception("Mapping of the AMPL model is invalid!")
            self.log.info("Mapping structure validation is successful!")
            mapping[mapping.OBJECTIVE_VALUE] = objective.value()
            mapping[mapping.RUNNING_TIME] = time.time() - self.start_timestamp
            return mapping
        elif result_str == 'limit':
            self.log.info("Some limit criteria has been reached!")
            # NOTE: There might be a feasible solution which is worse than the specified MIP gap, and is feasible.
            mapping[mapping.RUNNING_TIME] = time.time() - self.start_timestamp
            return mapping
        elif result_str == 'failure':
            self.log.warn("Failure in AMPL model!")
            return mapping
        elif '?' in result_str:
            # happens for example in case of too big model for a demo license
            self.log.warn("Question mark '?' in AMPL result!")
            return mapping
        else:
            self.log.error("Unhandled AMPL result variant!")
            raise NotImplementedError("Unhandled AMPL result variant!")

    def solve(self):
        """
        Calls the AMPL solve function and handles exceptions and warnings.

        :return:
        """
        # NOTE: error and warning handling are done by AMPLErrorHandler
        self.log.info("Starting AMPL solver...")
        self.start_timestamp = time.time()
        self.ampl.solve()
        objective = self.ampl.getObjective("Total_cost")
        try:
            # the demo license (above 300 constraints/variables) fails here, raising runtime error
            obj_message = objective.message()
            obj_result = objective.result()
            obj_value = objective.value()
        except RuntimeError as re:
            obj_message = traceback.format_exc()
            obj_result = "?"
            obj_value = "N/A"
        self.log.info("AMPL solver finished:\n"
                      "\t\t\tresult: {}\n"
                      "\t\t\tmessage: {}\n"
                      "\t\t\tobjective value: {}\n".format(obj_result, obj_message, obj_value))
        return self.construct_mapping(objective)



