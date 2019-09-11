from placement import mapper
from placement import checker


class VolatileResourcesChecker(checker.AbstractChecker):

    def __init__(self):
        super(VolatileResourcesChecker, self).__init__()

    def check_infra(self, infra) -> bool:
        """


        :param infra:
        :type infra: simulator.generate_service.InfrastructureGMLGraph
        :return:
        """
        return infra.check_graph()

    def check_ns(self, ns) -> bool:
        """


        :param ns:
        :type ns: simulator.generate_service.ServiceGMLGraph
        :return:
        """
        return ns.check_graph()


class ConstructiveMapperFromFractional(mapper.AbstractMapper):

    def __init__(self, checker: checker.AbstractChecker):
        super(ConstructiveMapperFromFractional, self).__init__(checker)

    # TODO: maybe return a mapping structure as a class? (we could move retrieving mapping info to this class instead of static mapper functions)
    def map(self, infra, ns) -> dict:
        pass

