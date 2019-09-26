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

# temporal parameters
# interval length between t0 and t1
param interval_length > 0;
set subintervals := 1..interval_length;

#coverage probabilities of the mobile cluster by the APs at subintervals
param prob_AP {ap in APs, t_k in subintervals} >=0.0, <=1.0;
# required coverage probability of the cluster
param coverage_threshold >=0.0, <=1.0;

# policies to map VNFs into infrastructure nodes
param policy {v in vertices[serviceGraph], N in vertices[infraGraph]} binary;

# battery parameters
param max_used_battery {N in mobiles} >=0.0, <=1.0;
param min_used_battery {N in mobiles} >=0.0, <=1.0;
param battery_threshold >=0.0, <=1.0;

# mapping variable: VNF v is mapped to infra node N
var X {v in vertices[serviceGraph], N in vertices[infraGraph]} binary;
# AP selection variable at time subinterval t_k
var AP_x {ap in APs, t_k in subintervals} binary;

minimize Total_cost:
    sum {v in vertices[serviceGraph], N in vertices[infraGraph]}
         X[v, N] * demands[v] * cost_unit_demand[N];

subject to Max_resources {N in vertices[infraGraph]}:
    sum {v in vertices[serviceGraph]}  X[v, N] * demands[v] <= resources[N];

subject to Map_to_one_place {v in vertices[serviceGraph]}:
    sum {N in vertices[infraGraph]}  X[v, N] = 1;

subject to Map_to_policies {v in vertices[serviceGraph], N in vertices[infraGraph]}:
    X[v, N] <= policy[v, N];

subject to Single_AP_selection {t_k in subintervals}:
    sum {ap in APs} AP_x[ap, t_k] = 1;

subject to AP_coverage_threshold {t_k in subintervals}:
    sum {ap in APs} AP_x[ap, t_k] *  prob_AP[ap, t_k] >= coverage_threshold;

# TODO: syntax error here somewhere
subject to battery {N in mobiles}:
    max_used_battery[N] - ((sum {v in vertices[serviceGraph]}  X[v, N] * demands[v])/resources[N])*(max_used_battery[N] - min_used_battery[N]) >= battery_threshold;
