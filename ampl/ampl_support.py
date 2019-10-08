import logging
import sys
from rainbow_logging_handler import RainbowLoggingHandler

from graphs.generate_service import InfrastructureGMLGraph, ServiceGMLGraph
from ampl.graph2ampl import get_complete_ampl_model_data


class AMPLSolverSupport(object):

    def __init__(self, ampl_model_path, service_instance : ServiceGMLGraph, substrate_network : InfrastructureGMLGraph,
                 optimization_kwargs : dict, log = None):
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
        self.log.info("Parsing to AMPL is successful!")

    def solve(self):
        """
        Calls the AMPL solve function and handles exceptions and warnings.

        :return:
        """
        # TODO
        self.log.info("Starting AMPL solver...")
        self.ampl.solve()
        self.log.info("AMPL solver finished!")


