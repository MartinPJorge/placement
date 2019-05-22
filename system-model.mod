set graph;
# we meed to specify the which graphs we want to work with
param serviceGraph in graph, symbolic;
param infraGraph in graph, symbolic;

#general graph functions
set vertices {graph};
set edges {g in graph} within (vertices[g] cross vertices[g]);

#subsets of infastructure
set APs within vertices[infraGraph];
set servers within vertices[infraGraph];
set mobiles within vertices[infraGraph];

# parameters defining input
param resources {N in vertices[infraGraph]} >= 0;
param demands {v in vertices[serviceGraph]} >= 0;
param cost_unit_demand {N in vertices[infraGraph]} >= 0;

# mapping variable: VNF v is mapped to infra node N
var X {v in vertices[serviceGraph], N in vertices[infraGraph]} binary;

minimize Total_cost:
    sum {v in vertices[serviceGraph], N in vertices[infraGraph]}
         X[v, N] * demands[v] * cost_unit_demand[N];

subject to Max_resources {N in vertices[infraGraph]}:
    sum {v in vertices[serviceGraph]}  X[v, N] * demands[v] <= resources[N];

subject to Map_to_one_place {v in vertices[serviceGraph]}:
    sum {N in vertices[infraGraph]}  X[v, N] = 1;
