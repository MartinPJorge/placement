import logging
import sys
from rainbow_logging_handler import RainbowLoggingHandler

import amplpy

from graphs.generate_service import InfrastructureGMLGraph, ServiceGMLGraph
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
        self.ampl.setErrorHandler(AMPLErrorHandler(self.log))
        if export_ampl_data_path is not None:
            # NOTE: Full zero rows/columns are not shown anywhere in the .dat file???
            self.log.info("Saving the generated AMPL data to file path {}".format(export_ampl_data_path))
            self.ampl.exportData(export_ampl_data_path)
        self.log.info("Parsing to AMPL is successful!")

    def solve(self):
        """
        Calls the AMPL solve function and handles exceptions and warnings.

        :return:
        """
        # NOTE: error and warning handling are done by AMPLErrorHandler
        self.log.info("Starting AMPL solver...")
        self.ampl.solve()
        self.log.info("AMPL solver finished!")


