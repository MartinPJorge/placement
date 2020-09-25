Creator "igraph version 1.2.4 Mon May 13 10:12:31 2019"
Version 1
graph
[
  directed 0
  node
  [
    id 0
	resource 10
	cost 10
    name "cell1"
    type "AP"
    lon -3.73811
    lat 40.256661
    cpu 1
    mem 0
    disk 0
    reliability 1
    radio "LTE"
    radioCost 20
    resCost 0
  ]
  node
  [
    id 1
	resource 10
	cost 10
    name "cell2"
    type "AP"
    lon -3.762818
    lat 40.257889
    cpu 1
    mem 0
    disk 0
    reliability 1
    radio "LTE"
    radioCost 20
    resCost 0
  ]
  node
  [
    id 2
	resource 10
	cost 10
    name "cell3"
    type "AP"
    lon -3.760941
    lat 40.260452
    cpu 1
    mem 0
    disk 0
    reliability 1
    radio "LTE"
    radioCost 20
    resCost 0
  ]
  node
  [
    id 3
	resource 10
	cost 10
    name "cell4"
    type "AP"
    lon -3.752824
    lat 40.271225
    cpu 1
    mem 0
    disk 0
    reliability 1
    radio "LTE"
    radioCost 20
    resCost 0
  ]
  node
  [
    id 4
	resource 10
	cost 10
    name "cell5"
    type "AP"
    lon -3.753695
    lat 40.263814
    cpu 1
    mem 0
    disk 0
    reliability 1
    radio "LTE"
    radioCost 20
    resCost 0
  ]
  node
  [
    id 5
	resource 10
	cost 10
    name "cell6"
    type "AP"
    lon -3.755264
    lat 40.268784
    cpu 1
    mem 0
    disk 0
    reliability 1
    radio "LTE"
    radioCost 20
    resCost 0
  ]
  node
  [
    id 6
	resource 10
	cost 10
    name "m1_0"
    type "server"
    lon -3.75204221690003
    lat 40.2613578838582
    cpu 0
    mem 0
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  node
  [
    id 7
	resource 10
	cost 10
    name "m2_0"
    type "server"
    lon -3.75204221690003
    lat 40.2613578838582
    cpu 0
    mem 0
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  node
  [
    id 8
	resource 10
	cost 10
    name "m3_0"
    type "server"
    lon -3.75204221690003
    lat 40.2613578838582
    cpu 0
    mem 0
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  node
  [
    id 9
	resource 10
	cost 10
    name "m3_rep_0"
    type "server"
    lon -3.75204221690003
    lat 40.2613578838582
    cpu 0
    mem 0
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  node
  [
    id 10
	resource 10
	cost 10
    name "dell_m1_server_0"
    type "server"
    lon -3.75204221690003
    lat 40.2613578838582
    cpu 2
    mem 20
    disk 100
    reliability 1
    radio ""
    radioCost 0
    resCost 100
  ]
  node
  [
    id 11
	resource 10
	cost 10
    name "dell_m2_server_0"
    type "server"
    lon -3.75204221690003
    lat 40.2613578838582
    cpu 2
    mem 20
    disk 100
    reliability 1
    radio ""
    radioCost 0
    resCost 100
  ]
  node
  [
    id 12
	resource 10
	cost 10
    name "fogEndpoint_test_fogNode_1"
    type "mobile"
    lon -3.75591113449374
    lat 40.2753689393847
    cpu 1
    mem 20
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  node
  [
    id 13
	resource 10
	cost 10
    name "fogEndpoint_test_fogNode_2"
    type "mobile"
    lon -3.74711856588699
    lat 40.2628525915245
    cpu 1
    mem 20
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  node
  [
    id 16
	resource 10
	cost 10
    name "test_fogNode_1"
    type "mobile"
    lon -3.76228051489926
    lat 40.2668251875245
    cpu 2
    mem 20
    disk 0
    reliability 1
    radio ""
    radioCost 0
    resCost 0
  ]
  edge
  [
    source 6
    target 0
    bandwidth 10
    bandwidthUnits "Gb/s"
    distance 1292.77
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 6
    target 1
    bandwidth 10
    bandwidthUnits "Gb/s"
    distance 992.68
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 6
    target 2
    bandwidth 10
    bandwidthUnits "Gb/s"
    distance 762.19
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 6
    target 3
    bandwidth 10
    bandwidthUnits "Gb/s"
    distance 1097.65
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 6
    target 4
    bandwidth 10
    bandwidthUnits "Gb/s"
    distance 306.71
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 6
    target 5
    bandwidth 10
    bandwidthUnits "Gb/s"
    distance 868.77
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 7
    target 6
    bandwidth 300
    bandwidthUnits "Gb/s"
    distance 0
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 8
    target 7
    bandwidth 6
    bandwidthUnits "Tb/s"
    distance 0
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 9
    target 8
    bandwidth 6
    bandwidthUnits "Tb/s"
    distance 0
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 9
    target 7
    bandwidth 6
    bandwidthUnits "Tb/s"
    distance 0
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 10
    target 6
    bandwidth 12
    bandwidthUnits "Mbps"
    distance 0
    distanceUnits "meter"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 11
    target 7
    bandwidth 12
    bandwidthUnits "Mbps"
    distance 0
    distanceUnits "meter"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 12
    target 0
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 2568.87
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 12
    target 1
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 2027.6
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 12
    target 2
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 1710.53
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 12
    target 3
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 529.53
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 12
    target 4
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 1296.78
    distanceUnits "meters"
    reliability 0.9
    trafficCost 9
  ]
  edge
  [
    source 12
    target 5
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 733.25
    distanceUnits "meters"
    reliability 0.8
    trafficCost 8
  ]
  edge
  [
    source 13
    target 0
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 1028.43
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 13
    target 1
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 1442.37
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 13
    target 2
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 1203.43
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 13
    target 3
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 1048.28
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 13
    target 4
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 568.44
    distanceUnits "meters"
    reliability 0.9
    trafficCost 9
  ]
  edge
  [
    source 13
    target 5
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 954.97
    distanceUnits "meters"
    reliability 0.8
    trafficCost 8
  ]
  edge
  [
    source 16
    target 0
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 2341.98
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 16
    target 1
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 993.32
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 16
    target 2
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 716.76
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 16
    target 3
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 939.75
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 16
    target 4
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 801.91
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
  edge
  [
    source 16
    target 5
    bandwidth 20
    bandwidthUnits "Mpbs"
    distance 634.12
    distanceUnits "meters"
    reliability 1
    trafficCost 10
  ]
]
