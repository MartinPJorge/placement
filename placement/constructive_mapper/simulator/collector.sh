#!/bin/bash - 
#===============================================================================
#
#          FILE: collector.sh
# 
#         USAGE: ./collector.sh 
# 
#   DESCRIPTION: from a plotting.log file, it extracts the JSON with every
#                experiment
# 
#       OPTIONS: ---
#  REQUIREMENTS: ---
#          BUGS: ---
#         NOTES: ---
#        AUTHOR: YOUR NAME (), 
#  ORGANIZATION: 
#       CREATED: 08/10/20 13:03
#      REVISION:  ---
#===============================================================================

set -o nounset                              # Treat unset variables as an error

if [ $# -ne 6 ]; then
    echo "Specify mapping and feasibility JSONs"
    echo "m_cost_json m_time_json m_handovers_json f_cost_json f_time_json f_handovers_json"
    exit 1
fi


# mapping JSONs
m_cost_json="$1"
m_time_json="$2"
m_handovers_json="$3"
# feasibility JSONs
f_cost_json="$4"
f_time_json="$5"
f_handovers_json="$6"
jsons=( $m_cost_json $m_time_json $m_handovers_json $f_cost_json $f_time_json $f_handovers_json )

plot_log="results/plotting.log"

exp_map_lines=( `grep -rni "to be plo" $plot_log  | cut -d':' -f1` )
exp_feas_lines=( `grep -rni "INF: Feasibility" $plot_log  | cut -d':' -f1` )
exp_name_lines=( `grep -rni "Saving pl" $plot_log  | cut -d':' -f1` )

#echo "exp_map_lines ${#exp_map_lines[@]} ${exp_map_lines[@]}"
#echo "exp_feas_lines ${#exp_feas_lines[@]} ${exp_feas_lines[@]}"
#echo "exp_name_lines ${#exp_name_lines[@]} ${exp_name_lines[@]}"

# Initialize JSONs
for json in $jsons; do
    echo -e "{\n" > $json
done

for i in `seq 0 $(( ${#exp_map_lines[@]} - 1 ))`; do
    # Print experiment key, e.g., "ampl-cost-sfcs-1"
    exp_name=`tail --lines=+${exp_name_lines[i]} $plot_log | head -n1 |\
        grep -oe "[a-Z0-9\-]\+\.png" | grep -oe "[a-Z0-9\-]\+" | head -n1`;

    # Select to which JSON file it is dumped
    echo $i $exp_name
    if [ `echo $exp_name | grep "cost"` ]; then
        out_json=$m_cost_json; feas_json=$f_cost_json;
    elif [ `echo $exp_name | grep "handovers"` ]; then
        out_json=$m_handovers_json; feas_json=$f_handovers_json;
    elif [ `echo $exp_name | grep "runtime"` ]; then
        out_json=$m_time_json; feas_json=$f_time_json;
    fi



    # Print the experiment key
    key="\"$exp_name\":"
    if [ `cat $out_json | wc -l ` -gt 2 ]; then
        key=",$key"
    fi
    echo $key >> $out_json
    echo $key >> $feas_json

    # Dump the experiment mapping JSON
    echo " $out_json"
    map_span=$(( exp_feas_lines[i] - exp_map_lines[i] - 1 ))
    echo "  $map_span lines ${exp_map_lines[i]}-${exp_feas_lines[i]} " 
    tail --lines=+$(( exp_map_lines[i] + 1 )) $plot_log |\
        head -n$map_span >> $out_json

    # Dump the experiment feasibility JSON
    echo " $feas_json"
    feas_span=$(( exp_name_lines[i] - exp_feas_lines[i] - 1 ))
    echo "  $feas_span lines from ${exp_feas_lines[i]}-${exp_name_lines[i]}"
    tail --lines=+$(( exp_feas_lines[i] + 1 )) $plot_log |\
        head -n$feas_span >> $feas_json

done


# finalize JSONs
for json in $jsons; do
    echo -e "\n}" >> $json
done


