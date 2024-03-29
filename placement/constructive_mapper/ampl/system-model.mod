set graph;
# we meed to specify the which graphs we want to work with
param infraGraph in graph, symbolic;
param serviceGraph in graph, symbolic;

#general graph functions
set vertices {graph};
set edges {g in graph} within (vertices[g] cross vertices[g]);

#subsets of infastructure
set APs within vertices[infraGraph];
set servers within vertices[infraGraph];
set mobiles within vertices[infraGraph];
# Significantly Reduce the number of constraints much modifications in parsing and .dat
set nf_hosting_nodes := servers union mobiles;

# defining the master robot inside the cluster
param master in mobiles, symbolic;

# subsets of service
set SFCs;
set SFC_paths {sfc in SFCs} within edges[serviceGraph];
param SFC_max_delays {sfc in SFCs} >= 0;

# parameters defining input
param resources {N in vertices[infraGraph]} >= 0;
param demands {v in vertices[serviceGraph]} >= 0;
param cost_unit_demand {N in vertices[infraGraph]} >= 0;
param cost_using_AP {ap in APs} >= 0;

# temporal parameters
# interval length between t0 and t1
param interval_length > 0;
set subintervals := 1..interval_length;

#coverage probabilities of the mobile cluster by the APs at subintervals
param prob_AP {ap in APs, t_k in subintervals} >=0.0, <=1.0;
# required coverage probability of the cluster
param coverage_threshold >=0.0, <=1.0;

# policies to map VNFs into infrastructure nodes
# NOTE: introducing the set 'nf_hosting_nodes', policies on mappings to AP-s wont have effect (before it was excluded by demands).
param policy {v in vertices[serviceGraph], N in vertices[infraGraph]} binary;

# battery parameters
param unloaded_battery_alive_prob {N in mobiles} >=0.0, <=1.0;
param full_loaded_battery_alive_prob {N in mobiles} >=0.0, <=1.0;
param battery_threshold >=0.0, <=1.0;

# delay parameters
param AP_mobile_delay {ap in APs} >= 0;
param AP_server_delay {ap in APs, s in servers} >= 0;
param server_server_delay {s in servers, r in servers} >= 0;
param mobile_mobile_delay {m in mobiles, n in mobiles} >= 0;

# mapping variable: VNF v is mapped to infra node N
var X {v in vertices[serviceGraph], N in nf_hosting_nodes} binary;
# AP selection variable at time subinterval t_k
var AP_x {ap in APs, t_k in subintervals} binary;

# delay variables for each of the three cases: mobile2mobile, mobile2server, server2server
var delay_mobile_fixed {m in mobiles, s in servers, t_k in subintervals} = mobile_mobile_delay[m, master] + sum {ap in APs} AP_x[ap, t_k]*(AP_mobile_delay[ap] + AP_server_delay[ap,s]);
var delay {N1 in nf_hosting_nodes, N2 in nf_hosting_nodes, t_k in subintervals} =
	if N1 in mobiles and N2 in servers then delay_mobile_fixed[N1, N2, t_k]
	else if N1 in servers and N2 in mobiles then delay_mobile_fixed[N2, N1, t_k]
	else if N1 in mobiles and N2 in mobiles then mobile_mobile_delay[N1, N2]
	else if N1 in servers and N2 in servers then server_server_delay[N1, N2];
# if we have problems in amount of variables, merge delay constraints in one

# continuous variable to eliminate X * X type constraints.
var Y {v1 in vertices[serviceGraph], N1 in nf_hosting_nodes, v2 in vertices[serviceGraph], N2 in nf_hosting_nodes} >= 0, <= 1;

minimize Total_cost:
    sum {v in vertices[serviceGraph], N in nf_hosting_nodes}
         X[v, N] * demands[v] * cost_unit_demand[N] + 
    sum {ap in APs, t_k in subintervals} AP_x[ap, t_k] * cost_using_AP[ap];

subject to Max_resources {N in nf_hosting_nodes}:
    sum {v in vertices[serviceGraph]}  X[v, N] * demands[v] <= resources[N];

subject to Map_to_one_place {v in vertices[serviceGraph]}:
    sum {N in nf_hosting_nodes}  X[v, N] = 1;

subject to Map_to_policies {v in vertices[serviceGraph], N in nf_hosting_nodes}:
    X[v, N] <= policy[v, N];

subject to Single_AP_selection {t_k in subintervals}:
    sum {ap in APs} AP_x[ap, t_k] = 1;

subject to AP_coverage_threshold {t_k in subintervals}:
    sum {ap in APs} AP_x[ap, t_k] *  prob_AP[ap, t_k] >= coverage_threshold;

subject to battery {N in mobiles}:
    resources[N] > 0 ==> unloaded_battery_alive_prob[N] - ((sum {v in vertices[serviceGraph]}  X[v, N] * demands[v])/resources[N])*(unloaded_battery_alive_prob[N] - full_loaded_battery_alive_prob[N]) >= battery_threshold;

subject to SFC_delays {sfc in SFCs, t_k in subintervals}:
    sum {(v1, v2) in SFC_paths[sfc]} sum {N1 in nf_hosting_nodes, N2 in nf_hosting_nodes} Y[v1, N1, v2, N2] * delay[N1, N2, t_k] <= SFC_max_delays[sfc];

subject to product_elimination_1 {v1 in vertices[serviceGraph], N1 in nf_hosting_nodes, v2 in vertices[serviceGraph], N2 in nf_hosting_nodes}:
    Y[v1, N1, v2, N2] <= X[v1, N1];

subject to product_elimination_2 {v1 in vertices[serviceGraph], N1 in nf_hosting_nodes, v2 in vertices[serviceGraph], N2 in nf_hosting_nodes}:
    Y[v1, N1, v2, N2] <= X[v2, N2];

subject to product_elimination_3 {v1 in vertices[serviceGraph], N1 in nf_hosting_nodes, v2 in vertices[serviceGraph], N2 in nf_hosting_nodes}:
    Y[v1, N1, v2, N2] >= X[v1, N1] + X[v2, N2] - 1;