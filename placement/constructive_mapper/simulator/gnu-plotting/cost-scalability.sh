#!/bin/bash - 
#===============================================================================
#
#          FILE: cost-scalability.sh
# 
#         USAGE: ./cost-scalability.sh 
# 
#   DESCRIPTION: 
# 
#       OPTIONS: ---
#  REQUIREMENTS: ---
#          BUGS: ---
#         NOTES: ---
#        AUTHOR: YOUR NAME (), 
#  ORGANIZATION: 
#       CREATED: 08/10/20 10:42
#      REVISION:  ---
#===============================================================================

set -o nounset                              # Treat unset variables as an error

ampl_jsons='ampl_solution.json'
heuristic_solution='heuristic_solution.json'
soa_solution='soa_solution.json'

aux_plot_dir='/tmp'



for sim in `ls -d ../results/scalability_test/[0-9]*`; do
    a
done

