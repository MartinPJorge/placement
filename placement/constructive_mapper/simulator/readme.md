# Reproduce experiment plots


## Delay experiments
1. generate the log with experiments info

```bash
python3 plot_results.py e2e_delay_effect
```
2. collect info inside the log and generate JSON files
```bash
./collector.sh /tmp/mcost.json\  # mappings' costs
               /tmp/mtime.json\  # mappings' runtime
               /tmp/mhands.json\ # mappings' handovers
               /tmp/fcost.json\  # feasibility
               /tmp/ftime.json\  # feasibility (redundant)
               /tmp/fhands.json  # feasibility (redundant)
```
3. copy the extracted JSONs to plot
```bash
cp /tmp/mcost.json exp-delay-variation-cost.json      
cp /tmp/mtime.json exp-delay-variation-runtime.json
```
4. just leave plotted experiments. Enter inside
     * exp-delay-variation-cost.json; and
     * exp-delay-variation-handovers.json
   rename keys as follow:
```txt
"ampl-{cost,runtime}-sfcs-1" --> "AMPL"
"soa-{cost,runtime}-sfcs-1" --> "FMC"
"heuristic-{cost,runtime}-sfcs-1-impr-1" --> "impr-1"
```
5. produce the plots
```bash
# Plot cost in delay variation (20 experiment each)
# Note: in the /tmp/f*.json the user sees that there are
#       20 experiment repetitions, thus the number below
python3 plot_results.py exp-delay-variation-cost.json\
    service.sfc_delays 20 "Cost Unit" linear True
# Handovers in delay variation
python3 plot_results.py exp-delay-variation-handovers.json\
    service.sfc_delays 1 "Number of handovers" linear True
```

 
## Coverage threshold variation experiments
1. generate the log with experiments info

```bash
python3 plot_results.py coverage_threshold_variation
```
2. collect info inside the log and generate JSON files
```bash
./collector.sh /tmp/mcost.json\  # mappings' costs
               /tmp/mtime.json\  # mappings' runtime
               /tmp/mhands.json\ # mappings' handovers
               /tmp/fcost.json\  # feasibility
               /tmp/ftime.json\  # feasibility (redundant)
               /tmp/fhands.json  # feasibility (redundant)
```
3. copy the extracted JSONs to plot
```bash
cp /tmp/mcost.json exp-coverage-variation-cost.json      
cp /tmp/mtime.json exp-coverage-variation-runtime.json
```
4. just leave plotted experiments. Enter inside
     * exp-coverage-variation-cost.json; and
     * exp-coverage-variation-runtime.json
   rename keys as follow:
```txt
"ampl-{cost,handovers}" --> "AMPL"
"heuristic-{cost,handovers}-impr-{1,2}" --> "impr-{1,2}"
"soa-{cost,handovers}" --> "FMC"
```
5. produce the plots
```bash
# Plot cost in delay variation (20 experiment each)
python3 plot_results.py exp-coverage-variation-cost.json\
    optimization.coverage_threshold 20 "Cost Units" linear True
python3 plot_results.py exp-coverage-variation-runtime.json\
    optimization.coverage_threshold 1 "Runtime [s]" log True 
```


## Scalability test
1. generate the log with experiments info

```bash
python3 plot_results.py scalability_test
```
2. collect info inside the log and generate JSON files
```bash
./collector.sh /tmp/mcost.json\  # mappings' costs
               /tmp/mtime.json\  # mappings' runtime
               /tmp/mhands.json\ # mappings' handovers
               /tmp/fcost.json\  # feasibility
               /tmp/ftime.json\  # feasibility (redundant)
               /tmp/fhands.json  # feasibility (redundant)
```
3. copy the extracted JSONs to plot
```bash
cp /tmp/mcost.json exp-scalability-cost.json      
cp /tmp/mtime.json exp-scalability-runtime.json
```
4. just leave plotted experiments. Enter inside
     * exp-scalability-cost.json; and
     * exp-scalability-runtime.json
   rename keys as follow:
```txt
"ampl-{cost,runtime}" --> "AMPL"
"heuristic-{cost,runtime}-impr-{1,2}" --> "impr-{1,2}"
"soa-{cost,runtime}" --> "FMC"
```
5. produce the plots
```bash
# Cplot cost in #NFs variation
python3 plot_results.py exp-scalability-cost.json\
    service.mobile_nfs_per_sfc 14 "Cost Units" linear True
# plot runtime in #NFs variation
python3 plot_results.py exp-scalability-runtime.json\
    service.mobile_nfs_per_sfc 1 "Runtime [s]" log True
```
## Scalability test
1. generate the log with experiments info

```bash
python3 plot_results.py scalability_test
```
2. collect info inside the log and generate JSON files
```bash
./collector.sh /tmp/mcost.json\  # mappings' costs
               /tmp/mtime.json\  # mappings' runtime
               /tmp/mhands.json\ # mappings' handovers
               /tmp/fcost.json\  # feasibility
               /tmp/ftime.json\  # feasibility (redundant)
               /tmp/fhands.json  # feasibility (redundant)
```
3. copy the extracted JSONs to plot
```bash
cp /tmp/mcost.json exp-scalability-cost.json      
cp /tmp/mtime.json exp-scalability-runtime.json
```
4. just leave plotted experiments. Enter inside
     * exp-scalability-cost.json; and
     * exp-scalability-runtime.json
   rename keys as follow:
```txt
"ampl-{cost,runtime}" --> "AMPL"
"heuristic-{cost,runtime}-impr-{1,2}" --> "impr-{1,2}"
"soa-{cost,runtime}" --> "FMC"
```
5. produce the plots
```bash
# Cplot cost in #NFs variation
python3 plot_results.py exp-scalability-cost.json\
    service.mobile_nfs_per_sfc 14 "Cost Units" linear True
# plot runtime in #NFs variation
python3 plot_results.py exp-scalability-runtime.json\
    service.mobile_nfs_per_sfc 1 "Runtime [s]" log True
```



## Battery threshold test
1. generate the log with experiments info

```bash
python3 plot_results.py mobile_nf_loads_small_sweep
```
 * it might crash at a certain point, thus, it is necessary to remove spurous
   data in the log. Go to `results/plotting.log` and look for the last line
   like
```txt
70882 2020-10-09 15:32:46,757.Plotter.INF: Saving plot results/mobile_nf_loads_small_sweep/plots/soa-feas-battery_th-0.812.png      ...
```
 * this refers to the latest experiment. Just remove from line 70883.
2. collect info inside the log and generate JSON files
```bash
./collector.sh /tmp/mcost.json\  # mappings' costs
               /tmp/mtime.json\  # mappings' runtime
               /tmp/mhands.json\ # mappings' handovers
               /tmp/fcost.json\  # feasibility
               /tmp/ftime.json\  # feasibility (redundant)
               /tmp/fhands.json  # feasibility (redundant)
```
3. copy the extracted JSONs to plot
```bash
cp /tmp/mcost.json exp-battery-th-cost.json      
```
4. just leave plotted experiments. Enter inside
     * exp-battery-th-cost.json
   rename keys as follow:
```txt
"ampl-cost-battery_th-0.7184.png" --> "AMPL-battery_th-72%"
"heuristic-cost-battery_th-0.7184-impr-1.png" --> "impr-1-battery_th-72%"
"ampl-cost-battery_th-0.7496.png" --> "AMPL-battery_th-75%"
"heuristic-cost-battery_th-0.7496-impr-1.png" --> "impr-1-battery_th-75%"
"soa-cost-battery_th-0.7184.png" --> "FMC"
```
5. produce the plots
```bash
# Cplot cost in #NFs variation
python3 plot_results.py exp-battery-th-cost.json\
    optimization.battery_threshold 14 "Cost Units" linear True
```
6. The feasibility reported in the plot is not correct for the FMC,
   because the algorithm is agnostic to the battery restriction.
   Therefore, we perform an external check to determine what was
   the probability of meeting a battery threshold:
```bash
python3 check_battery.py 0.72
```
   and it will check if all battery probs where above/equal 0.72 in
   every experiment repetition.





----------

Note: in case the `plot_results.py` script can't read the JSON files,
puting them under `/tmp` solves the problem.
