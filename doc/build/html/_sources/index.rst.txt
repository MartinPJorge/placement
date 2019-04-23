.. placement documentation master file, created by
   sphinx-quickstart on Tue Apr  2 12:09:59 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Home
=====================================
This package is a collection of algorithms to solve the Virtual Network Embedding (VNE) problem [VNE]_.

The problem consists in assigning each element of a network service to the elements of the network infrastructure, which has computational nodes (servers, fog nodes as raspberry PIs, ...) and physical links (ethernet, fiber, ...).

It relies on networkx_ for the generation of the network service and the infrastructure. Both graphs must contain the necessary graph's edges and nodes attributes, to pass the checks of the classes present in the :doc:`checker` module.

Example
-------

Let's see a simple example consisting where we want to deploy a network service consisting of an access point and a virtual cache:

.. code-block:: python

   import networkx as nx

   ns = nx.DiGraph()
   ns.add_node('ap', cpu=1, mem=4, disk=100, rats=['LTE'],
       location={'center': (39.128380, -1.080805), 'radius': 20})
   ns.add_node('vcache', cpu=1, mem=1, disk=400)
   ns.add_edge('ap', 'vcache', bw=59, delay=100)


If such service must be mapped on top of a simple infrastructure consisting of an antenna `a1` and a host `h2` connected to it:

.. code-block:: python

   infra = nx.DiGraph()
   cost = {'cpu': 2, 'disk': 2.3, 'mem': 4}
   infra.add_node('a1', cpu=2, mem=16, disk=1024, rats=['LTE', 'MMW'],
       location=(39.1408046,-1.0795603), cost=cost)
   infra.add_node('h2', cpu=1, mem=8, disk=512, cost=cost)
   infra.add_edge('a1', 'h2', bw=100, delay=1, cost=30)


Then we just have to create a graph checker and assign it to the mapper to be used.
In our case we've created an infrastructure graph as the ones expected by :class:`CheckBasicDigraphs<placement.checker.CheckBasicDigraphs>`, therefore, we request the mapping as follows:

.. code-block:: python

    from placement import mapper
    from placement import checker

    checker = checker.CheckBasicDigraphs()
    mapper = mapper.GreedyCostMapper(checker=checker, k=2)
    mapping = mapper.map(infra=infra, ns=ns)
    >>> mapping['ap']
    'a1'
    >>> mapping[('ap', 'vcache')]
    ['a1', 'h2']


.. _networkx: https://networkx.github.io/


Documentation
-------------
.. only:: html

    :Release: |version|
    :Date: |today|

.. toctree::
    mapper
    checker

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`




.. [VNE] Amaldi, Edoardo, et al. "On the computational complexity of the virtual network embedding problem." Electronic Notes in Discrete Mathematics 52 (2016): 213-220.
