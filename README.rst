Placement
=========
This python package intends to be a collection of VNF
placement algorithms running on top of networkx package. Each placement
algorithm is contained within the mapper module as a class inheriting from the
AbstractMapper. Every AbstractMapper has an associated AbstractChecker to
ensure that received graphs contain the required information.

